from collections import defaultdict
from collections.abc import Sequence

from engrama.domain.entities import Chunk, Decision, Doc, Edge, EdgeKind, Node, Repo
from engrama.domain.services.document_chunker import DocumentChunker
from engrama.domain.services.repository_graph import RepositoryGraph
from engrama.domain.services.route_mention_matcher import MentionReport
from engrama.domain.value_objects import Evidence, NodeRef, Provenance, Validity
from engrama.domain.value_objects.document_facts import DocumentFile, DocumentKind

README = "README.md"


class DocumentationGraphBuilder:
    """Monta a camada de documentacao de um repo a partir dos documentos lidos.

    Tudo aqui vem de extracao deterministica: o documento existe no commit, o
    pedaco saiu daquelas linhas e a rota esta escrita no texto. Quem ligar um
    documento a um conceito ou resumi-lo e a parte que usa LLM, com origem e
    confianca proprias (principio 1 do doc de fundamentacao).

    `DOCUMENTED_IN` so nasce de duas evidencias que nao exigem interpretacao:
    o README da raiz documenta o repo, e uma rota escrita no texto documenta
    aquele endpoint. Dizer que um documento qualquer "documenta" determinado
    modulo e leitura de conteudo, nao extracao.
    """

    def __init__(self, chunker: DocumentChunker) -> None:
        self._chunker = chunker

    def repository(
        self,
        repo: Repo,
        documents: Sequence[DocumentFile],
        mentions: MentionReport,
        validity: Validity,
    ) -> RepositoryGraph:
        nodes: dict[NodeRef, Node] = {repo.ref: repo}
        edges: list[Edge] = []
        for document in documents:
            node = self._document_node(document)
            nodes[node.ref] = node
            edges.append(
                self._edge(EdgeKind.PART_OF, node.ref, repo.ref, [document.evidence], validity)
            )
            if document.path == README:
                edges.append(
                    self._edge(
                        EdgeKind.DOCUMENTED_IN, repo.ref, node.ref, [document.evidence], validity
                    )
                )
            for chunk in self._chunks(document):
                nodes[chunk.ref] = chunk
                evidence = Evidence.in_code(
                    document.repo, document.path, self._commit(document), chunk.first_line
                )
                edges.append(
                    self._edge(EdgeKind.PART_OF, chunk.ref, node.ref, [evidence], validity)
                )

        grouped: dict[tuple[NodeRef, NodeRef], list[Evidence]] = defaultdict(list)
        documents_by_path = {document.path: document for document in documents}
        for match in mentions.matches:
            document = documents_by_path.get(match.mention.path)
            if document is None:
                continue
            target = self._document_node(document).ref
            grouped[(match.endpoint.ref, target)].append(match.mention.evidence)
        for (source, target), evidence in grouped.items():
            edges.append(self._edge(EdgeKind.DOCUMENTED_IN, source, target, evidence, validity))

        return RepositoryGraph(tuple(nodes.values()), tuple(edges))

    def _chunks(self, document: DocumentFile) -> list[Chunk]:
        markdown = document.path.endswith(".md")
        return [
            Chunk(
                repo=document.repo,
                path=document.path,
                index=chunk.index,
                text=chunk.text,
                first_line=chunk.first_line,
                last_line=chunk.last_line,
                heading=chunk.heading,
            )
            for chunk in self._chunker.chunks(document.text, markdown=markdown)
        ]

    @staticmethod
    def _document_node(document: DocumentFile) -> Doc | Decision:
        if document.kind is DocumentKind.DECISION:
            return Decision(document.repo, document.path, document.title, document.status)
        return Doc(document.repo, document.path, document.title)

    @staticmethod
    def _commit(document: DocumentFile) -> str:
        """O commit vem da evidencia do proprio documento, que a leitura ja fixou."""
        return document.evidence.commit or ""

    @staticmethod
    def _edge(
        kind: EdgeKind,
        source: NodeRef,
        target: NodeRef,
        evidence: Sequence[Evidence],
        validity: Validity,
    ) -> Edge:
        return Edge(kind, source, target, Provenance.extracted(*evidence), validity)
