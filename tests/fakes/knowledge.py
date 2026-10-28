import re
from datetime import datetime

from engrama.application.dto.knowledge import ChunkHit, IndexedDocument
from engrama.application.ports.knowledge import KnowledgeIndex
from engrama.domain.entities import Chunk, EdgeKind
from engrama.domain.value_objects import NodeKind
from tests.fakes.graph import InMemoryGraph

_WORDS = re.compile(r"\w+", re.UNICODE)
_DOCUMENTS = (NodeKind.DOC, NodeKind.DECISION)


class InMemoryKnowledgeIndex(KnowledgeIndex):
    """Busca sobre o grafo em memoria, pontuando por palavra em comum.

    Le os mesmos nos e arestas abertas que o adapter do Neo4j le: um pedaco so
    aparece se a aresta `PART_OF` dele para o documento esta aberta. A nota nao
    e a do Lucene (nao tem BM25 nem radical), entao o contrato compartilhado so
    cobra o que os dois garantem: ordem por nota, limite e o que entra.
    """

    def __init__(self, graph: InMemoryGraph) -> None:
        self._graph = graph

    def search(self, query: str, limit: int = 10) -> list[ChunkHit]:
        terms = {word.lower() for word in _WORDS.findall(query)}
        if not terms or limit < 1:
            return []
        scored = []
        for chunk, document, ingested_at in self._chunks():
            words = {word.lower() for word in _WORDS.findall(f"{chunk.text} {chunk.heading}")}
            score = len(terms & words)
            if score:
                scored.append((score, chunk, document, ingested_at))
        scored.sort(key=lambda item: (-item[0], item[1].key))
        return [
            ChunkHit(
                repo=chunk.repo,
                path=chunk.path,
                first_line=chunk.first_line,
                last_line=chunk.last_line,
                heading=chunk.heading,
                text=chunk.text,
                score=float(score),
                document_title=document.title,
                document_kind=document.node_kind.value,
                ingested_at=ingested_at,
            )
            for score, chunk, document, ingested_at in scored[:limit]
        ]

    def documents(self) -> list[IndexedDocument]:
        chunks: dict[str, int] = {}
        for _, document, _ingested_at in self._chunks():
            chunks[document.key] = chunks.get(document.key, 0) + 1
        found = [
            IndexedDocument(
                repo=document.repo,
                path=document.path,
                kind=document.node_kind.value,
                title=document.title,
                chunks=chunks.get(document.key, 0),
            )
            for document in self._open_documents()
        ]
        return sorted(found)

    def _chunks(self) -> list[tuple[Chunk, object, datetime]]:
        documents = {document.ref: document for document in self._open_documents()}
        found = []
        for stored in self._graph.open_edges(EdgeKind.PART_OF):
            if stored.edge.source.kind is not NodeKind.CHUNK:
                continue
            document = documents.get(stored.edge.target)
            chunk = self._graph.nodes.get((NodeKind.CHUNK.value, stored.edge.source.key))
            if document is not None and chunk is not None:
                assert isinstance(chunk, Chunk)
                found.append((chunk, document, stored.edge.validity.ingested_at))
        return found

    def _open_documents(self) -> list:
        """Documentos com `PART_OF` aberta para o repo: o que vale hoje."""
        found = []
        for stored in self._graph.open_edges(EdgeKind.PART_OF):
            if stored.edge.source.kind not in _DOCUMENTS:
                continue
            node = self._graph.nodes.get((stored.edge.source.kind.value, stored.edge.source.key))
            if node is not None:
                found.append(node)
        return found
