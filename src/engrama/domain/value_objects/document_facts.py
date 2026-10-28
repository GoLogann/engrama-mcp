from dataclasses import dataclass
from enum import StrEnum

from engrama.domain.value_objects.http_route import HttpRoute
from engrama.domain.value_objects.provenance import Evidence

# Fatos que a leitura deterministica encontra nos documentos de um repo.
# Como os de `code_facts`, ainda nao sao nos nem arestas: o
# DocumentationGraphBuilder os transforma no grafo.


class DocumentKind(StrEnum):
    """Um documento comum ou um registro de decisao (ADR)."""

    DOC = "doc"
    DECISION = "decision"


@dataclass(frozen=True, slots=True)
class DocumentFile:
    """Um documento do repo com o texto ja mascarado pela politica de segredos.

    `title` sai do primeiro titulo do arquivo, ou do nome dele; `status` so
    existe em decisao, e sai da linha "Status:" do proprio documento.
    """

    repo: str
    path: str
    kind: DocumentKind
    title: str
    text: str
    evidence: Evidence
    status: str | None = None


@dataclass(frozen=True, slots=True)
class RouteMention:
    """Rota escrita no texto de um documento (`POST /api/v1/generate/batch`).

    E uma citacao, nao uma declaracao: o documento diz que a rota existe, e
    quem decide a qual endpoint ela corresponde e o RouteMentionMatcher.
    """

    repo: str
    path: str
    route: HttpRoute
    evidence: Evidence
