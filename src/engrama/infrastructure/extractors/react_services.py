from collections.abc import Collection

from tree_sitter import Node as SyntaxNode

from engrama.domain.entities import Stack
from engrama.domain.services import RouteNormalizer
from engrama.domain.value_objects.code_facts import CallSite
from engrama.infrastructure.extractors.base import ParsedFile, TreeSitterExtractor, walk


class ReactServiceExtractor(TreeSitterExtractor):
    """Chamadas HTTP feitas pelas funcoes cliente do frontend (por padrao
    `request` e `requestBlob`). O caminho e o primeiro argumento; o metodo vem
    da chave `method` do segundo, e o padrao e GET, como no `fetch`."""

    stack = Stack.TYPESCRIPT_REACT
    language = "tsx"
    suffixes = (".ts", ".tsx")

    def __init__(
        self,
        normalizer: RouteNormalizer,
        http_functions: Collection[str] = ("request", "requestBlob"),
    ) -> None:
        super().__init__(normalizer)
        self._http_functions = set(http_functions)

    def _is_test_file(self, name: str) -> bool:
        return name.endswith((".d.ts", ".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx"))

    def _extract_file(self, file: ParsedFile) -> None:
        constants = self._string_constants(file)
        for call in walk(file.root, "call_expression"):
            function = call.child_by_field_name("function")
            if function is None or file.text(function) not in self._http_functions:
                continue
            arguments = call.child_by_field_name("arguments").named_children
            if not arguments:
                continue
            paths = self._paths(file, arguments[0], constants)
            if not paths:
                file.warn(call, f"caminho nao resolvido: {file.text(arguments[0])[:60]}")
                continue
            method = self._method(file, arguments[1]) if len(arguments) > 1 else "GET"
            routes = {self._normalizer.route(method, file.spec.base_path, p) for p in paths}
            for route in sorted(routes, key=str):
                file.calls.append(CallSite(file.repo, file.module, route, file.evidence(call)))

    def _string_constants(self, file: ParsedFile) -> dict[str, str]:
        constants: dict[str, str] = {}
        for declaration in walk(file.root, "variable_declarator"):
            value = declaration.child_by_field_name("value")
            if value is not None and value.type in ("string", "template_string"):
                resolved = self._paths(file, value, constants)
                if len(resolved) == 1:
                    constants[file.text(declaration.child_by_field_name("name"))] = resolved[0]
        return constants

    def _paths(self, file: ParsedFile, node: SyntaxNode, constants: dict[str, str]) -> list[str]:
        """Valores possiveis do caminho. Substituicoes que nao sao constantes
        viram `${expr}`, e o normalizador as converte em parametro."""
        if node.type == "string":
            return ["".join(file.text(c) for c in node.named_children)]
        if node.type == "template_string":
            parts = []
            for child in node.named_children:
                if child.type == "template_substitution":
                    expression = file.text(child)[2:-1].strip()
                    parts.append(constants.get(expression, "${" + expression + "}"))
                else:
                    parts.append(file.text(child))
            return ["".join(parts)]
        if node.type == "ternary_expression":
            return [
                path
                for field in ("consequence", "alternative")
                for path in self._paths(file, node.child_by_field_name(field), constants)
            ]
        if node.type == "identifier" and file.text(node) in constants:
            return [constants[file.text(node)]]
        return []

    @staticmethod
    def _method(file: ParsedFile, options: SyntaxNode) -> str:
        if options.type != "object":
            return "GET"
        for pair in options.named_children:
            if pair.type == "pair" and file.text(pair.child_by_field_name("key")) == "method":
                return file.text(pair.child_by_field_name("value")).strip("'\"`")
        return "GET"
