from tree_sitter import Node as SyntaxNode

from engrama.domain.entities import Stack
from engrama.domain.value_objects.code_facts import DeclaredRoute
from engrama.infrastructure.extractors.base import ParsedFile, TreeSitterExtractor, walk

_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
_UNSUPPORTED = {"Any", "Handle", "Match"}
_ROUTER_TYPES = {"*gin.Engine", "*gin.RouterGroup", "gin.IRouter", "gin.IRoutes"}
_FUNCTIONS = ("function_declaration", "method_declaration", "func_literal")


class GinExtractor(TreeSitterExtractor):
    """Rotas registradas com `grupo.GET("/caminho", handler)`. O prefixo de
    cada grupo vem de `x := router.Group("prefixo")`, encadeado em ordem."""

    stack = Stack.GO_GIN
    language = "go"
    suffixes = (".go",)
    exclude_dirs = frozenset({"tests", "testdata", "vendor"})

    def _is_test_file(self, name: str) -> bool:
        return name.endswith("_test.go")

    def _extract_file(self, file: ParsedFile) -> None:
        for function in walk(file.root, *_FUNCTIONS):
            prefixes = self._router_parameters(file, function)
            if prefixes:
                self._read_body(file, function, prefixes)

    def _router_parameters(self, file: ParsedFile, function: SyntaxNode) -> dict[str, str]:
        parameters = function.child_by_field_name("parameters")
        prefixes: dict[str, str] = {}
        for declaration in walk(parameters, "parameter_declaration") if parameters else ():
            if file.text(declaration.child_by_field_name("type")) in _ROUTER_TYPES:
                prefixes[file.text(declaration.child_by_field_name("name"))] = ""
        return prefixes

    def _read_body(self, file: ParsedFile, function: SyntaxNode, prefixes: dict[str, str]) -> None:
        for node in walk(
            function, "short_var_declaration", "assignment_statement", "call_expression"
        ):
            if node.type == "call_expression":
                self._route(file, prefixes, node)
                continue
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            call = right.named_children[0] if right and right.named_children else None
            group = self._selector(file, call)
            if group and group[1] == "Group" and group[0] in prefixes:
                prefix = self._first_string(file, call) or ""
                prefixes[file.text(left)] = self._normalizer.join(prefixes[group[0]], prefix)

    def _route(self, file: ParsedFile, prefixes: dict[str, str], call: SyntaxNode) -> None:
        selector = self._selector(file, call)
        if not selector or selector[0] not in prefixes:
            return
        receiver, method = selector
        if method in _UNSUPPORTED:
            file.warn(call, f"{method} registra rota sem metodo fixo; nao extraida")
            return
        if method not in _METHODS:
            return
        path = self._first_string(file, call)
        if path is None:
            file.warn(call, "rota sem caminho literal")
            return
        arguments = call.child_by_field_name("arguments").named_children
        file.routes.append(
            DeclaredRoute(
                repo=file.repo,
                module=file.module,
                route=self._normalizer.route(method, prefixes[receiver], path),
                evidence=file.evidence(call),
                handler=file.text(arguments[-1]) if len(arguments) > 1 else None,
            )
        )

    @staticmethod
    def _selector(file: ParsedFile, call: SyntaxNode | None) -> tuple[str, str] | None:
        if call is None or call.type != "call_expression":
            return None
        function = call.child_by_field_name("function")
        if function is None or function.type != "selector_expression":
            return None
        return (
            file.text(function.child_by_field_name("operand")),
            file.text(function.child_by_field_name("field")),
        )

    @staticmethod
    def _first_string(file: ParsedFile, call: SyntaxNode) -> str | None:
        arguments = call.child_by_field_name("arguments")
        first = arguments.named_children[0] if arguments and arguments.named_children else None
        if first is None or first.type not in ("interpreted_string_literal", "raw_string_literal"):
            return None
        return file.text(first)[1:-1]
