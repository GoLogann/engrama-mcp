import logging
import re

from neo4j import Driver

from engrama.application.dto.knowledge import ChunkHit, IndexedDocument
from engrama.application.ports.knowledge import (
    BY_MIXED,
    BY_VECTOR,
    BY_WORD,
    Embedder,
    EmbeddingUnavailable,
    KnowledgeIndex,
)

logger = logging.getLogger(__name__)

CHUNK_INDEX = "chunk_text"
VECTOR_INDEX = "chunk_embedding"

# A consulta vai para o Lucene, que trata `/`, `?`, `:` e `-` como sintaxe. A
# pergunta e reduzida as palavras (e assim que o analisador quebra o texto
# indexado tambem, entao nao se perde nada) e cada palavra vai entre aspas.
# As aspas sao o que neutraliza as palavras-operador: sem elas, uma pergunta
# com "AND", "OR" ou "NOT" solto faz o Lucene recusar a consulta inteira.
_WORDS = re.compile(r"\w+", re.UNICODE)

# Documento com a aresta PART_OF aberta: o que vale hoje (ADR 0009). As duas
# consultas projetam as mesmas colunas, para o resultado ser montado por um
# caminho so.
_PROJECTION = """
MATCH (node)-[r:PART_OF {open: true}]->(d)
WHERE d:Doc OR d:Decision
RETURN node.key AS key, node.repo AS repo, node.path AS path,
       node.first_line AS first_line, node.last_line AS last_line,
       node.heading AS heading, node.text AS text,
       d.title AS title, labels(d)[0] AS kind, r.ingested_at AS ingested_at,
       score AS score
ORDER BY score DESC, repo, path, first_line
LIMIT $limit
"""

_LEXICAL = f"""
CALL db.index.fulltext.queryNodes('{CHUNK_INDEX}', $query) YIELD node, score
{_PROJECTION}
"""

_VECTOR = f"""
CALL db.index.vector.queryNodes('{VECTOR_INDEX}', $limit, $vector) YIELD node, score
{_PROJECTION}
"""

# OPTIONAL porque documento vazio nao tem pedaco.
_DOCUMENTS = """
MATCH (d)-[:PART_OF {open: true}]->(:Repo)
WHERE d:Doc OR d:Decision
OPTIONAL MATCH (c:Chunk)-[:PART_OF {open: true}]->(d)
RETURN d.repo AS repo, d.path AS path, labels(d)[0] AS kind, d.title AS title,
       count(c) AS chunks
ORDER BY repo, path
"""


class Neo4jKnowledgeIndex(KnowledgeIndex):
    """Busca na camada de documentacao, por significado ou por palavra.

    O ranking e o indice vetorial. A metade por palavra existe como reserva,
    nao como metade de uma fusao: medido nas fontes das perguntas de ouro, o
    vetor acha 91% dos arquivos em k=10 contra 82% da palavra, e **ganha
    tambem da fusao por RRF** (86%), em todo tamanho de lista testado. A
    razao e estrutural: com as vagas divididas entre as duas listas, um
    achado que so o vetor ve, em 6o lugar, nao cabe na saida. As medicoes
    estao no ADR 0011.

    Sem `embedder` a busca cai para palavra, e `ranking()` passa a dizer
    isso. A reserva e para nao exigir chave de API de quem so quer rodar o
    projeto; ela responde pior, e por isso nunca e escolhida em silencio.
    """

    def __init__(
        self,
        driver: Driver,
        embedder: Embedder | None = None,
        database: str = "neo4j",
    ) -> None:
        self._driver = driver
        self._embedder = embedder
        self._database = database
        self._degraded = False
        self._used: set[str] = set()

    def ranking(self) -> str:
        """O motor desta rodada, somando o que cada busca de fato usou.

        Uma rodada pode degradar no meio: as primeiras consultas vao por vetor
        e, esgotado o teto de taxa, as seguintes vao por palavra. Reportar so
        o estado final chamaria de `palavra` numeros que o vetor produziu.
        """
        if self._embedder is None:
            return BY_WORD
        if len(self._used) > 1:
            return BY_MIXED
        return next(iter(self._used), BY_WORD if self._degraded else BY_VECTOR)

    def search(self, query: str, limit: int = 10) -> list[ChunkHit]:
        words = _WORDS.findall(query)
        if not words or limit < 1:
            return []
        vector = self._embed(query)
        if vector is None:
            self._used.add(BY_WORD)
            return self._lexical(words, limit)
        self._used.add(BY_VECTOR)
        rows = self._run(_VECTOR, vector=vector, limit=limit)
        return [self._hit(row) for row in rows]

    def _embed(self, query: str) -> list[float] | None:
        """O vetor da pergunta, ou `None` quando a busca cai para palavra.

        Provedor indisponivel nao derruba a busca, mas tambem nao passa em
        silencio: avisa e marca a instancia como degradada, para `ranking()`
        parar de dizer `vetor`. Qualquer outro erro sobe — chave errada ou
        indice ausente e defeito de configuracao, nao motivo para responder
        pior sem ninguem saber.
        """
        if self._embedder is None:
            return None
        try:
            return list(self._embedder.embed_query(query))
        except EmbeddingUnavailable as error:
            self._degraded = True
            logger.warning(
                "Embeddings indisponiveis (%s): esta busca e as seguintes caem para busca "
                "por palavra, que acha menos fontes (82%% contra 91%% em k=10).",
                error,
            )
            return None

    def _lexical(self, words: list[str], limit: int) -> list[ChunkHit]:
        terms = " ".join(f'"{word}"' for word in words)
        return [self._hit(row) for row in self._run(_LEXICAL, query=terms, limit=limit)]

    def documents(self) -> list[IndexedDocument]:
        records, _, _ = self._driver.execute_query(
            _DOCUMENTS, database_=self._database, routing_="r"
        )
        return [
            IndexedDocument(
                repo=row["repo"],
                path=row["path"],
                kind=row["kind"],
                title=row["title"],
                chunks=row["chunks"],
            )
            for row in records
        ]

    def _run(self, cypher: str, **parameters: object) -> list[dict]:
        """O parametro se chama `cypher`, e nao `query`: a consulta lexical
        passa um parametro de nome `query` para o Cypher, e os dois colidiam."""
        records, _, _ = self._driver.execute_query(
            cypher, database_=self._database, routing_="r", **parameters
        )
        return [dict(row) for row in records]

    @staticmethod
    def _hit(row: dict) -> ChunkHit:
        return ChunkHit(
            repo=row["repo"],
            path=row["path"],
            first_line=row["first_line"],
            last_line=row["last_line"],
            heading=row["heading"] or "",
            text=row["text"],
            score=row["score"],
            document_title=row["title"],
            document_kind=row["kind"],
            ingested_at=row["ingested_at"].to_native(),
        )
