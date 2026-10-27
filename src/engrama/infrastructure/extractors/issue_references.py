import re
from collections.abc import Collection

from engrama.application.dto.ingestion import CodeFacts, RepositorySpec
from engrama.application.ports.sources import CodeExtractor, SourceTree
from engrama.domain.value_objects import Evidence
from engrama.domain.value_objects.code_facts import IssueReference
from engrama.infrastructure.extractors.base import TEST_DIRS, module_of

_CODE_SUFFIXES = (".py", ".go", ".ts", ".tsx", ".js", ".dart")
_NUMBER_LIST = r"#(?P<first>\d+)(?P<rest>(?:\s*(?:,|/|\be\b|\band\b)\s*#\d+)*)"


class IssueReferenceExtractor(CodeExtractor):
    """Citacoes a issues em codigo: `issue #7`, `issues #12 e #13` (do proprio
    repo) e `phishforge-api #5 e #6` (de outro repo do catalogo). Um `#7`
    solto nao conta: e ambiguo demais."""

    def __init__(self, known_repos: Collection[str]) -> None:
        names = "|".join(re.escape(n) for n in sorted(known_repos, key=len, reverse=True))
        self._same_repo = re.compile(rf"(?i)\bissues?\s*{_NUMBER_LIST}")
        self._other_repo = re.compile(rf"(?<![\w/-])(?P<repo>{names})\s*{_NUMBER_LIST}")

    def supports(self, spec: RepositorySpec) -> bool:
        return True

    def extract(self, tree: SourceTree, spec: RepositorySpec) -> CodeFacts:
        repo = spec.repo
        references: list[IssueReference] = []
        for path in tree.files(_CODE_SUFFIXES, TEST_DIRS):
            for number, line in enumerate(tree.read(path).splitlines(), start=1):
                evidence = Evidence.in_code(repo.name, path, repo.commit, number)
                for issue_repo, issue in self._references(line, repo.name):
                    references.append(
                        IssueReference(repo.name, module_of(path), issue_repo, issue, evidence)
                    )
        return CodeFacts(issues=tuple(dict.fromkeys(references)))

    def _references(self, line: str, own_repo: str) -> list[tuple[str, int]]:
        found: list[tuple[str, int]] = []
        for pattern, repo_of in (
            (self._same_repo, lambda m: own_repo),
            (self._other_repo, lambda m: m.group("repo")),
        ):
            for match in pattern.finditer(line):
                numbers = [match.group("first"), *re.findall(r"#(\d+)", match.group("rest"))]
                found += [(repo_of(match), int(n)) for n in numbers]
        return found
