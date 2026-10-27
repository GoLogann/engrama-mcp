from abc import abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import ClassVar

from tree_sitter import Node as SyntaxNode
from tree_sitter_language_pack import get_parser

from engrama.application.dto.ingestion import CodeFacts, RepositorySpec
from engrama.application.ports.sources import CodeExtractor, SourceTree
from engrama.domain.entities import Stack
from engrama.domain.services import ROOT_MODULE, RouteNormalizer
from engrama.domain.value_objects import Evidence
from engrama.domain.value_objects.code_facts import CallSite, DeclaredRoute

TEST_DIRS = frozenset({"test", "tests", "__tests__", "testdata"})


def module_of(path: str) -> str:
    parent = str(PurePosixPath(path).parent)
    return ROOT_MODULE if parent == "." else parent


def walk(node: SyntaxNode, *types: str) -> Iterator[SyntaxNode]:
    """Percorre a subarvore em ordem de codigo-fonte, devolvendo os nos dos tipos pedidos."""
    stack = [node]
    while stack:
        current = stack.pop()
        if not types or current.type in types:
            yield current
        stack.extend(reversed(current.children))


@dataclass
class ParsedFile:
    spec: RepositorySpec
    path: str
    source: bytes
    root: SyntaxNode
    routes: list[DeclaredRoute] = field(default_factory=list)
    calls: list[CallSite] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)

    @property
    def repo(self) -> str:
        return self.spec.repo.name

    @property
    def module(self) -> str:
        return module_of(self.path)

    def text(self, node: SyntaxNode | None) -> str:
        if node is None:
            return ""
        return self.source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    def evidence(self, node: SyntaxNode) -> Evidence:
        return Evidence.in_code(
            self.repo, self.path, self.spec.repo.commit, node.start_point[0] + 1
        )

    def warn(self, node: SyntaxNode, message: str) -> None:
        self.diagnostics.append(f"{self.repo}/{self.path}:{node.start_point[0] + 1}: {message}")


class TreeSitterExtractor(CodeExtractor):
    """Template method: escolhe os arquivos da stack, faz o parse e delega a
    leitura de cada arquivo para `_extract_file`. Cada subclasse conhece so
    os padroes do seu framework."""

    stack: ClassVar[Stack]
    language: ClassVar[str]
    suffixes: ClassVar[tuple[str, ...]]
    exclude_dirs: ClassVar[frozenset[str]] = TEST_DIRS

    def __init__(self, normalizer: RouteNormalizer) -> None:
        self._normalizer = normalizer
        self._parser = get_parser(self.language)

    def supports(self, spec: RepositorySpec) -> bool:
        return spec.repo.stack is self.stack

    def extract(self, tree: SourceTree, spec: RepositorySpec) -> CodeFacts:
        modules: set[str] = set()
        routes: list[DeclaredRoute] = []
        calls: list[CallSite] = []
        diagnostics: list[str] = []
        for path in tree.files(self.suffixes, self.exclude_dirs):
            if self._is_test_file(PurePosixPath(path).name) or not self._in_scope(path):
                continue
            modules.add(module_of(path))
            source = tree.read(path).encode("utf-8")
            parsed = ParsedFile(spec, path, source, self._parser.parse(source).root_node)
            self._extract_file(parsed)
            routes += parsed.routes
            calls += parsed.calls
            diagnostics += parsed.diagnostics
        return CodeFacts(
            modules=frozenset(modules),
            routes=tuple(routes),
            calls=tuple(calls),
            diagnostics=tuple(diagnostics),
        )

    def _is_test_file(self, name: str) -> bool:
        return False

    def _in_scope(self, path: str) -> bool:
        return True

    @abstractmethod
    def _extract_file(self, file: ParsedFile) -> None:
        """Le um arquivo e acrescenta rotas, chamadas e diagnosticos em `file`."""
