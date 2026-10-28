import uuid
from collections.abc import Collection

from engrama.application.dto.documentation import (
    DocumentSummary,
    IndexingReport,
    RepositoryDocuments,
)
from engrama.application.ports.graph import GraphWriter, StructureReader
from engrama.application.ports.sources import RepositoryCatalog
from engrama.application.ports.system import Clock
from engrama.application.use_cases.read_repository_documents import ReadRepositoryDocuments
from engrama.domain.services import DocumentationGraphBuilder, RepositoryGraph, RouteMentionMatcher
from engrama.domain.value_objects import NodeKind, Validity
from engrama.domain.value_objects.document_facts import DocumentKind, RouteMention


def documentation_owner(repo: str) -> str:
    """O dono das arestas da documentacao de um repo.

    Camada propria de dono (ADR 0009 e 0010): a aposentadoria de arestas e
    por dono, entao indexar documentos nao pode encerrar as arestas da
    estrutura do mesmo repo, nem o contrario.
    """
    return f"{repo}:docs"


class IndexDocuments:
    """Monta e grava a camada de documentacao dos repos do catalogo.

    Depende da estrutura ja estar no grafo para ligar uma rota citada num
    documento ao endpoint que ela descreve; sem estrutura, indexa os
    documentos e avisa que nenhum endpoint era conhecido.
    """

    def __init__(
        self,
        catalog: RepositoryCatalog,
        read: ReadRepositoryDocuments,
        matcher: RouteMentionMatcher,
        builder: DocumentationGraphBuilder,
        writer: GraphWriter,
        structure: StructureReader,
        clock: Clock,
    ) -> None:
        self._catalog = catalog
        self._read = read
        self._matcher = matcher
        self._builder = builder
        self._writer = writer
        self._structure = structure
        self._clock = clock

    def execute(self, only: Collection[str] = ()) -> IndexingReport:
        catalog = self._catalog.load()
        now = self._clock.now()
        names = catalog.only(only)
        specs = [spec for spec in catalog.repos if spec.repo.name in names]
        endpoints = self._structure.endpoints()

        graphs: dict[str, RepositoryGraph] = {}
        summaries: list[DocumentSummary] = []
        diagnostics: list[str] = []
        unmatched: list[RouteMention] = []
        ambiguous: list[RouteMention] = []
        for spec in specs:
            documents = self._read.execute(spec)
            mentions = self._matcher.match(list(documents.facts.mentions), endpoints)
            graph = self._builder.repository(
                repo=spec.repo,
                documents=documents.facts.documents,
                mentions=mentions,
                validity=Validity.starting(documents.committed_at, ingested_at=now),
            )
            graphs[documentation_owner(spec.repo.name)] = graph
            summaries.append(self._summary(documents, graph))
            diagnostics += documents.facts.diagnostics
            unmatched += mentions.unmatched
            ambiguous += [mention for mention, _ in mentions.ambiguous]

        self._writer.ensure_schema()
        self._writer.write(graphs, run_id=uuid.uuid4().hex, at=now)

        return IndexingReport(
            repos=tuple(summaries),
            known_endpoints=len(endpoints),
            unmatched=tuple(unmatched),
            ambiguous=tuple(ambiguous),
            diagnostics=tuple(diagnostics),
        )

    @staticmethod
    def _summary(documents: RepositoryDocuments, graph: RepositoryGraph) -> DocumentSummary:
        kinds = [document.kind for document in documents.facts.documents]
        return DocumentSummary(
            repo=documents.spec.repo.name,
            documents=kinds.count(DocumentKind.DOC),
            decisions=kinds.count(DocumentKind.DECISION),
            chunks=sum(1 for node in graph.nodes if node.node_kind is NodeKind.CHUNK),
            # Endpoints distintos, nao arestas: o mesmo endpoint citado em dois
            # documentos rende duas arestas e continua sendo um endpoint.
            endpoints_documented=len(
                {edge.source for edge in graph.edges if edge.source.kind is NodeKind.ENDPOINT}
            ),
            redactions=len(documents.redactions),
        )
