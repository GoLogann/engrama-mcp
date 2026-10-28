from dataclasses import dataclass
from datetime import datetime

from engrama.application.dto.ingestion import RepositorySpec
from engrama.domain.value_objects.document_facts import (
    DocumentFile,
    DocumentIssueCitation,
    RouteMention,
)


@dataclass(frozen=True, slots=True)
class DocumentFacts:
    """O que a leitura de documentos achou num repo. Como em `CodeFacts`,
    `diagnostics` registra o que foi visto e nao interpretado."""

    documents: tuple[DocumentFile, ...] = ()
    mentions: tuple[RouteMention, ...] = ()
    issues: tuple[DocumentIssueCitation, ...] = ()
    diagnostics: tuple[str, ...] = ()

    def merged(self, other: "DocumentFacts") -> "DocumentFacts":
        return DocumentFacts(
            documents=self.documents + other.documents,
            mentions=self.mentions + other.mentions,
            issues=self.issues + other.issues,
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
    # Issues citadas nos documentos do repo. A ontologia sempre permitiu
    # `Doc`/`Decision` -> `Issue`; so a extracao nao as criava.
    issues: int = 0


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
    # Pedacos que ficaram com vetor. Menor que o total de pedacos significa
    # que a metade vetorial da busca nao enxerga o resto.
    vectors: int = 0
