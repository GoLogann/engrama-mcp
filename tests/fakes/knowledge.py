import hashlib
import math
import re
from collections.abc import Mapping, Sequence
from datetime import datetime

from engrama.application.dto.knowledge import ChunkHit, IndexedDocument
from engrama.application.ports.knowledge import (
    BY_VECTOR,
    BY_WORD,
    Embedder,
    KnowledgeIndex,
    Vector,
    VectorStore,
)
from engrama.domain.entities import Chunk, EdgeKind
from engrama.domain.value_objects import NodeKind
from tests.fakes.graph import InMemoryGraph

_WORDS = re.compile(r"\w+", re.UNICODE)
_DOCUMENTS = (NodeKind.DOC, NodeKind.DECISION)


class FakeEmbedder(Embedder):
    """Embeddings deterministicos, sem rede: saco de palavras em baldes.

    Nao imita a Voyage (nao sabe que "migrations" e `flyway` falam do mesmo
    assunto), mas imita as duas propriedades de que os testes dependem:
    texto parecido da vetor parecido, e texto sem palavra em comum da vetor
    quase ortogonal. Usa `hashlib` e nao `hash()`, que e aleatorizado por
    processo e faria o mesmo teste passar e falhar entre rodadas.
    """

    def __init__(self, dimensions: int = 1024) -> None:
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> Vector:
        return self._vector(text)

    def _vector(self, text: str) -> Vector:
        numbers = [0.0] * self._dimensions
        for word in _WORDS.findall(text.lower()):
            digest = hashlib.sha1(word.encode()).digest()
            numbers[int.from_bytes(digest[:4]) % self._dimensions] += 1.0
        norm = math.sqrt(sum(number * number for number in numbers))
        if not norm:
            # Vetor nulo nao tem direcao, e o indice vetorial do Neo4j o
            # recusa. Um balde fixo faz o texto sem palavra ter um lugar.
            numbers[0] = 1.0
            norm = 1.0
        return tuple(number / norm for number in numbers)


class InMemoryVectorStore(VectorStore):
    """Guarda os vetores por chave de pedaco, como o Neo4j guardaria.

    Ignora chave que nao esta no grafo, que e o que o adapter real faz com
    `MATCH`: vetor solto nunca cria no.
    """

    def __init__(self, graph: InMemoryGraph) -> None:
        self._graph = graph
        self.vectors: dict[str, Vector] = {}

    def store(self, vectors: Mapping[str, Vector]) -> int:
        stored = 0
        for key, vector in vectors.items():
            if (NodeKind.CHUNK.value, key) in self._graph.nodes:
                self.vectors[key] = vector
                stored += 1
        return stored


class InMemoryKnowledgeIndex(KnowledgeIndex):
    """Busca sobre o grafo em memoria, pelos mesmos dois caminhos do Neo4j.

    Espelha o adapter real de proposito: ranqueia por cosseno quando ha
    embedder e por palavra em comum quando nao ha. Sem isso o contrato
    deixaria de ser compartilhado — o fake garantiria "palavra inexistente
    nao traz nada", que e propriedade de busca lexical e nenhuma busca
    vetorial tem.

    A nota nao e a do Lucene (nao tem BM25 nem radical), entao o contrato so
    cobra o que os dois garantem: ordem por nota, limite e o que entra.
    """

    def __init__(self, graph: InMemoryGraph, embedder: Embedder | None = None) -> None:
        self._graph = graph
        self._embedder = embedder

    def ranking(self) -> str:
        return BY_WORD if self._embedder is None else BY_VECTOR

    def search(self, query: str, limit: int = 10) -> list[ChunkHit]:
        terms = {word.lower() for word in _WORDS.findall(query)}
        if not terms or limit < 1:
            return []
        rows = {found[0].key: found for found in self._chunks()}

        if self._embedder is None:
            asked = None
            scored = []
            for key, (chunk, _document, _at) in rows.items():
                words = {word.lower() for word in _WORDS.findall(f"{chunk.text} {chunk.heading}")}
                score = len(terms & words)
                if score:
                    scored.append((float(score), key))
        else:
            asked = self._embedder.embed_query(query)
            scored = [
                (_cosine(asked, self._embedder.embed_documents([chunk.text])[0]), key)
                for key, (chunk, _document, _at) in rows.items()
            ]

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [self._hit(rows[key], score) for score, key in scored[:limit]]

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

    @staticmethod
    def _hit(found: tuple[Chunk, object, datetime], score: float) -> ChunkHit:
        chunk, document, ingested_at = found
        return ChunkHit(
            repo=chunk.repo,
            path=chunk.path,
            first_line=chunk.first_line,
            last_line=chunk.last_line,
            heading=chunk.heading,
            text=chunk.text,
            score=score,
            document_title=document.title,
            document_kind=document.node_kind.value,
            ingested_at=ingested_at,
        )

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


def _cosine(left: Vector, right: Vector) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))
