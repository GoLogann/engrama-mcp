import re
from collections.abc import Collection

from engrama.application.dto.ingestion import CodeFacts, RepositorySpec
from engrama.application.ports.sources import CodeExtractor, SourceTree
from engrama.domain.services import IssueCitationReader
from engrama.domain.value_objects import Evidence
from engrama.domain.value_objects.code_facts import IssueReference
from engrama.infrastructure.extractors.base import TEST_DIRS, module_of

_CODE_SUFFIXES = (".py", ".go", ".ts", ".tsx", ".js", ".dart")
_COMMENT_MARKER = re.compile(r"^\s*(?://+|/?\*+|#+)\s?")


def _comment_text(line: str) -> str:
    """O texto de uma linha de comentario sem o marcador, ou vazio se nao for comentario.
    So uma linha de comentario continua a frase da linha anterior; codigo nao."""
    marker = _COMMENT_MARKER.match(line)
    return line[marker.end() :] if marker else ""


class IssueReferenceExtractor(CodeExtractor):
    """Prende as citacoes de issue encontradas no codigo ao modulo do arquivo.

    A leitura em si e do `IssueCitationReader` (dominio), compartilhada com a
    extracao de documentos: as duas reconhecem as mesmas formas e so diferem
    em onde a citacao e pendurada. Aqui, "logo depois" significa a proxima
    linha de *comentario* — codigo nao continua uma frase.
    """

    def __init__(self, known_repos: Collection[str]) -> None:
        self._reader = IssueCitationReader(known_repos)

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
                report = self._reader.read(
                    line, following, own_repo=repo.name, consumes=spec.consumes
                )
                evidence = Evidence.in_code(repo.name, path, repo.commit, number)
                references += [
                    IssueReference(
                        repo.name, module_of(path), citation.repo, citation.number, evidence
                    )
                    for citation in report.found
                ]
                diagnostics += [
                    f"{repo.name}/{path}:{number}: issue #{issue} citada como de outro repo, "
                    f"sem como resolver qual ({len(spec.consumes)} repos em consumes); "
                    f"citacao ignorada em vez de atribuida a {repo.name}"
                    for issue in report.unresolved
                ]
        return CodeFacts(issues=tuple(dict.fromkeys(references)), diagnostics=tuple(diagnostics))
