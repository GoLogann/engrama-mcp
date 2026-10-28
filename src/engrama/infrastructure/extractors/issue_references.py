import re
from collections.abc import Collection

from engrama.application.dto.ingestion import CodeFacts, RepositorySpec
from engrama.application.ports.sources import CodeExtractor, SourceTree
from engrama.domain.value_objects import Evidence
from engrama.domain.value_objects.code_facts import IssueReference
from engrama.infrastructure.extractors.base import TEST_DIRS, module_of

_CODE_SUFFIXES = (".py", ".go", ".ts", ".tsx", ".js", ".dart")
_NUMBER_LIST = r"#(?P<first>\d+)(?P<rest>(?:\s*(?:,|/|\be\b|\band\b)\s*#\d+)*)"
_COMMENT_MARKER = re.compile(r"^\s*(?://+|/?\*+|#+)\s?")

# O qualificador vem logo depois do numero, mas pode haver um participio no
# meio: "issue #38 aberta no front". Uma palavra so, para "issue #7 e o front
# tambem usa" nao virar citacao do front.
_QUALIFIER = r"^[\s,;(]*(?:\w+\s+)?(?:d[oa]|n[oa])\s+"
# "issue #5 do backend": o repo do servidor nao esta no texto, esta em `consumes`.
_BACKEND = re.compile(rf"(?i){_QUALIFIER}(?:back-?end|servidor)\b")
# Qualificador que aponta para outro repo sem nomea-lo de forma resolvivel:
# "do app", "no front". Quem consome este repo nao esta em `consumes` (que
# lista quem ele consome), entao nao da para resolver — e atribuir ao proprio
# repo seria gravar a issue errada com confianca alta.
_FOREIGN = re.compile(rf"(?i){_QUALIFIER}(?:app|aplicativo|front(?:-?end)?|mobile|cliente|site)\b")


def _numbers(match: re.Match[str]) -> list[int]:
    return [int(n) for n in (match.group("first"), *re.findall(r"#(\d+)", match.group("rest")))]


def _comment_text(line: str) -> str:
    """O texto de uma linha de comentario sem o marcador, ou vazio se nao for comentario.
    So uma linha de comentario continua a frase da linha anterior; codigo nao."""
    marker = _COMMENT_MARKER.match(line)
    return line[marker.end() :] if marker else ""


class IssueReferenceExtractor(CodeExtractor):
    """Citacoes a issues em codigo: `issue #7`, `issues #12 e #13` (do proprio
    repo) e `phishforge-api #5 e #6` (de outro repo do catalogo). Um `#7`
    solto nao conta: e ambiguo demais.

    `issue #N` vale para o repo do arquivo, a menos que logo depois (na mesma
    linha ou na linha de comentario seguinte) venha um qualificador:
    `do repo <nome>` / `do <nome>` aponta para esse repo do catalogo, e
    `do backend` aponta para o unico repo em `consumes`. Se houver zero ou
    varios, a citacao e ignorada e a extracao registra um diagnostico: gravar
    no repo errado, com confianca alta, seria pior que nao gravar.
    """

    def __init__(self, known_repos: Collection[str]) -> None:
        names = "|".join(re.escape(n) for n in sorted(known_repos, key=len, reverse=True))
        self._canonical = {name.lower(): name for name in known_repos}
        self._same_repo = re.compile(rf"(?i)\bissues?\s*{_NUMBER_LIST}")
        self._other_repo = re.compile(rf"(?<![\w/-])(?P<repo>{names})\s*{_NUMBER_LIST}")
        # A crase e as aspas aparecem em "no repositorio `phishing_quest`".
        self._named_after = re.compile(
            rf"(?i){_QUALIFIER}(?:repo(?:sit[óo]rio)?\s+)?[`'\"]?(?P<repo>{names})\b"
        )

    def supports(self, spec: RepositorySpec) -> bool:
        return True

    def extract(self, tree: SourceTree, spec: RepositorySpec) -> CodeFacts:
        repo = spec.repo
        references: list[IssueReference] = []
        diagnostics: list[str] = []
        for path in tree.files(_CODE_SUFFIXES, TEST_DIRS):
            lines = tree.read(path).splitlines()
            for number, line in enumerate(lines, start=1):
                following = _comment_text(lines[number]) if number < len(lines) else ""
                evidence = Evidence.in_code(repo.name, path, repo.commit, number)
                found, unresolved = self._references(line, following, spec)
                references += [
                    IssueReference(repo.name, module_of(path), issue_repo, issue, evidence)
                    for issue_repo, issue in found
                ]
                diagnostics += [
                    f"{repo.name}/{path}:{number}: issue #{issue} citada como de outro repo, "
                    f"sem como resolver qual ({len(spec.consumes)} repos em consumes); "
                    f"citacao ignorada em vez de atribuida a {repo.name}"
                    for issue in unresolved
                ]
        return CodeFacts(issues=tuple(dict.fromkeys(references)), diagnostics=tuple(diagnostics))

    def _references(
        self, line: str, following: str, spec: RepositorySpec
    ) -> tuple[list[tuple[str, int]], list[int]]:
        found: list[tuple[str, int]] = []
        unresolved: list[int] = []
        for match in self._same_repo.finditer(line):
            tail = f"{line[match.end() :]} {following}"
            target = self._target(tail, spec)
            if target is None:
                unresolved += _numbers(match)
            else:
                found += [(target, n) for n in _numbers(match)]
        for match in self._other_repo.finditer(line):
            found += [(match.group("repo"), n) for n in _numbers(match)]
        return found, unresolved

    def _target(self, tail: str, spec: RepositorySpec) -> str | None:
        """O repo dono da issue, ou `None` quando a citacao aponta para fora e
        nao da para dizer para onde.

        `None` nunca significa "assume o proprio repo": e exatamente o caso em
        que atribuir ao proprio seria gravar a issue errada com confianca
        alta. Vira diagnostico e a citacao nao entra no grafo.
        """
        if named := self._named_after.match(tail):
            return self._canonical[named.group("repo").lower()]
        if _BACKEND.match(tail):
            return spec.consumes[0] if len(spec.consumes) == 1 else None
        if _FOREIGN.match(tail):
            return None
        return spec.repo.name
