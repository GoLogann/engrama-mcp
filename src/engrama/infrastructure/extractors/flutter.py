from collections.abc import Collection

from tree_sitter import Node as SyntaxNode

from engrama.domain.entities import Stack
from engrama.domain.services import RouteNormalizer
from engrama.domain.value_objects.code_facts import CallSite
from engrama.infrastructure.extractors.base import ParsedFile, TreeSitterExtractor, walk

_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
_STRING_PREFIXES = ("r'''", 'r"""', "'''", '"""', "r'", 'r"', "'", '"')


def _dart_string(text: str) -> str:
    for prefix in _STRING_PREFIXES:
        quote = prefix.lstrip("r")
        if text.startswith(prefix) and text.endswith(quote):
            return text[len(prefix) : len(text) - len(quote)]
    return text


class FlutterExtractor(TreeSitterExtractor):
    """Chamadas montadas com `final url = helpers.buildUrl(url: '/caminho')`.
    O metodo vem da chamada HTTP que usa essa variavel na mesma funcao
    (`client.post(url, ...)`). O caminho base vem de `spec.base_path`."""

    stack = Stack.DART_FLUTTER
    language = "dart"
    suffixes = (".dart",)
    exclude_dirs = frozenset({"test", "integration_test", "build", ".dart_tool"})

    def __init__(
        self, normalizer: RouteNormalizer, url_builders: Collection[str] = ("buildUrl",)
    ) -> None:
        super().__init__(normalizer)
        self._url_builders = set(url_builders)

    def _in_scope(self, path: str) -> bool:
        return path.startswith("lib/")

    def _extract_file(self, file: ParsedFile) -> None:
        constants = self._string_constants(file)
        for definition in walk(file.root, "initialized_variable_definition"):
            values = [c for c in definition.children if c.type in ("identifier", "selector")]
            builder = next(
                (
                    n
                    for v in values
                    for n in walk(v, "identifier")
                    if file.text(n) in self._url_builders
                ),
                None,
            )
            if builder is None:
                continue
            path = self._url_argument(file, definition, constants)
            if path is None:
                file.warn(builder, "buildUrl sem caminho resolvido")
                continue
            variable = file.text(definition.child_by_field_name("name"))
            method = self._method_using(file, definition, variable)
            if method is None:
                file.warn(builder, f"nenhuma chamada HTTP usa '{variable}' na mesma funcao")
                continue
            route = self._canonical_route(file, builder, method, file.spec.base_path, path)
            if route is not None:
                file.calls.append(CallSite(file.repo, file.module, route, file.evidence(builder)))

    def _string_constants(self, file: ParsedFile) -> dict[str, str]:
        constants: dict[str, str] = {}
        for declaration in walk(file.root, "static_final_declaration"):
            name = next((c for c in declaration.children if c.type == "identifier"), None)
            value = next((c for c in declaration.children if c.type == "string_literal"), None)
            if name is not None and value is not None:
                constants[file.text(name)] = _dart_string(file.text(value))
        return constants

    def _url_argument(
        self, file: ParsedFile, definition: SyntaxNode, constants: dict[str, str]
    ) -> str | None:
        for argument in walk(definition, "named_argument"):
            label = next((c for c in argument.children if c.type == "label"), None)
            if label is None or file.text(label).rstrip(":").strip() != "url":
                continue
            value = argument.named_children[-1]
            if value.type == "string_literal":
                return _dart_string(file.text(value))
            return constants.get(file.text(value))
        return None

    def _method_using(self, file: ParsedFile, definition: SyntaxNode, variable: str) -> str | None:
        body = definition.parent
        while body is not None and body.type not in ("function_body", "block"):
            body = body.parent
        if body is None:
            return None
        for selector in walk(body, "unconditional_assignable_selector"):
            if selector.start_byte < definition.end_byte:
                continue
            name = file.text(selector.named_children[0]) if selector.named_children else ""
            arguments = selector.parent.next_named_sibling if selector.parent else None
            if name not in _HTTP_METHODS or arguments is None:
                continue
            first = next(walk(arguments, "argument"), None)
            if first is not None and file.text(first).strip() == variable:
                return name.upper()
        return None
