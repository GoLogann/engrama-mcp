from tree_sitter import Node as SyntaxNode

from engrama.domain.entities import Stack
from engrama.domain.value_objects.code_facts import DeclaredRoute
from engrama.infrastructure.extractors.base import ParsedFile, TreeSitterExtractor, walk

_METHODS = {"get", "post", "put", "patch", "delete"}
_ROUTER_FACTORIES = {"APIRouter", "FastAPI"}


class FastApiExtractor(TreeSitterExtractor):
    """Rotas declaradas com `@router.<metodo>("/caminho")`, somando o `prefix`
    do `APIRouter(prefix=...)` do mesmo arquivo."""

    stack = Stack.PYTHON_FASTAPI
    language = "python"
    suffixes = (".py",)

    def _is_test_file(self, name: str) -> bool:
        return name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"

    def _extract_file(self, file: ParsedFile) -> None:
        prefixes = self._router_prefixes(file)
        self._warn_on_include_prefix(file)
        for definition in walk(file.root, "decorated_definition"):
            for decorator in definition.children:
                if decorator.type == "decorator":
                    self._route(file, prefixes, decorator, definition)

    def _router_prefixes(self, file: ParsedFile) -> dict[str, str]:
        prefixes: dict[str, str] = {}
        for assignment in walk(file.root, "assignment"):
            right = assignment.child_by_field_name("right")
            if right is None or right.type != "call":
                continue
            factory = file.text(right.child_by_field_name("function")).split(".")[-1]
            if factory in _ROUTER_FACTORIES:
                name = file.text(assignment.child_by_field_name("left"))
                prefixes[name] = self._keyword_string(file, right, "prefix") or ""
        return prefixes

    def _warn_on_include_prefix(self, file: ParsedFile) -> None:
        for call in walk(file.root, "call"):
            function = file.text(call.child_by_field_name("function"))
            if function.endswith(".include_router") and self._keyword_string(file, call, "prefix"):
                file.warn(
                    call,
                    "include_router com prefix nao e suportado; rotas podem sair sem o prefixo",
                )

    def _route(
        self,
        file: ParsedFile,
        prefixes: dict[str, str],
        decorator: SyntaxNode,
        definition: SyntaxNode,
    ) -> None:
        call = next((c for c in decorator.named_children if c.type == "call"), None)
        if call is None:
            return
        function = call.child_by_field_name("function")
        if function is None or function.type != "attribute":
            return
        method = file.text(function.child_by_field_name("attribute"))
        router = file.text(function.child_by_field_name("object"))
        if method not in _METHODS or router not in prefixes:
            return
        arguments = call.child_by_field_name("arguments")
        path_node = next((a for a in arguments.named_children if a.type == "string"), None)
        if path_node is None:
            file.warn(decorator, "rota sem caminho literal")
            return
        handler = definition.child_by_field_name("definition")
        file.routes.append(
            DeclaredRoute(
                repo=file.repo,
                module=file.module,
                route=self._normalizer.route(
                    method, prefixes[router], self._string(file, path_node)
                ),
                evidence=file.evidence(decorator),
                handler=file.text(handler.child_by_field_name("name")) if handler else None,
            )
        )

    def _keyword_string(self, file: ParsedFile, call: SyntaxNode, keyword: str) -> str | None:
        arguments = call.child_by_field_name("arguments")
        for argument in arguments.named_children if arguments else ():
            if argument.type == "keyword_argument":
                value = argument.child_by_field_name("value")
                if (
                    file.text(argument.child_by_field_name("name")) == keyword
                    and value.type == "string"
                ):
                    return self._string(file, value)
        return None

    @staticmethod
    def _string(file: ParsedFile, node: SyntaxNode) -> str:
        return "".join(file.text(c) for c in node.named_children if c.type == "string_content")
