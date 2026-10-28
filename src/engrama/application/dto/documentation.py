from dataclasses import dataclass
from datetime import datetime

from engrama.application.dto.ingestion import RepositorySpec
from engrama.domain.value_objects.document_facts import DocumentFile, RouteMention


@dataclass(frozen=True, slots=True)
class DocumentFacts:
    """O que a leitura de documentos achou num repo. Como em `CodeFacts`,
    `diagnostics` registra o que foi visto e nao interpretado."""

    documents: tuple[DocumentFile, ...] = ()
    mentions: tuple[RouteMention, ...] = ()
    diagnostics: tuple[str, ...] = ()

    def merged(self, other: "DocumentFacts") -> "DocumentFacts":
        return DocumentFacts(
            documents=self.documents + other.documents,
            mentions=self.mentions + other.mentions,
            diagnostics=self.diagnostics + other.diagnostics,
        )


@dataclass(frozen=True, slots=True)
class RepositoryDocuments:
    """Os documentos de um repo, com o texto ja mascarado.

    `redactions` conta quantos valores a politica de segredos mascarou, por
    regra, para a mascara nunca agir em silencio.
    """

    spec: RepositorySpec
    committed_at: datetime
    facts: DocumentFacts
    redactions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DocumentSummary:
    repo: str
    documents: int
    decisions: int
    chunks: int
    endpoints_documented: int
    redactions: int


@dataclass(frozen=True, slots=True)
class IndexingReport:
    """`unmatched` e `ambiguous` nao sao defeito da extracao: uma rota escrita
    num documento que nenhum endpoint expoe e documentacao desalinhada do
    codigo, que e justamente um dos achados que a PoC quer mostrar."""

    repos: tuple[DocumentSummary, ...]
    known_endpoints: int
    unmatched: tuple[RouteMention, ...] = ()
    ambiguous: tuple[RouteMention, ...] = ()
    diagnostics: tuple[str, ...] = ()
