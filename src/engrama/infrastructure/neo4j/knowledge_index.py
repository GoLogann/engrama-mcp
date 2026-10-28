import re

from neo4j import Driver

from engrama.application.dto.knowledge import ChunkHit, IndexedDocument
from engrama.application.ports.knowledge import Embedder, KnowledgeIndex
from engrama.domain.services import ReciprocalRankFusion

CHUNK_INDEX = "chunk_text"
VECTOR_INDEX = "chunk_embedding"

# Quantos candidatos cada metade traz antes da fusao. Mais fundo que o `limit`
# pedido de proposito: um pedaco em 30o lugar na busca por palavra e em 2o na
# vetorial precisa estar nas duas listas para o RRF poder somar as posicoes.
_CANDIDATES = 50

# A consulta vai para o Lucene, que trata `/`, `?`, `:` e `-` como sintaxe. A
# pergunta e reduzida as palavras (e assim que o analisador quebra o texto
# indexado tambem, entao nao se perde nada) e cada palavra vai entre aspas.
# As aspas sao o que neutraliza as palavras-operador: sem elas, uma pergunta
# com "AND", "OR" ou "NOT" solto faz o Lucene recusar a consulta inteira.
_WORDS = re.compile(r"\w+", re.UNICODE)

# Documento com a aresta PART_OF aberta: o que vale hoje (ADR 0009). As duas
# metades da busca projetam as mesmas colunas, para o resultado ser montado
# por um caminho so.
_PROJECTION = """
MATCH (node)-[r:PART_OF {open: true}]->(d)
WHERE d:Doc OR d:Decision
RETURN node.key AS key, node.repo AS repo, node.path AS path,
       node.first_line AS first_line, node.last_line AS last_line,
       node.heading AS heading, node.text AS text,
       d.title AS title, labels(d)[0] AS kind, r.ingested_at AS ingested_at,
       score AS score
ORDER BY score DESC, repo, path, first_line
LIMIT $candidates
"""

_LEXICAL = f"""
CALL db.index.fulltext.queryNodes('{CHUNK_INDEX}', $query) YIELD node, score
{_PROJECTION}
"""

_VECTOR = f"""
CALL db.index.vector.queryNodes('{VECTOR_INDEX}', $candidates, $vector) YIELD node, score
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
    """Busca hibrida na camada de documentacao.

    Duas metades independentes: o indice de texto completo, com analisador
    portugues, e o indice vetorial. Elas acham coisas diferentes — a primeira
    exige a palavra, a segunda entende que "migrations" e `flyway` falam do
    mesmo assunto — e os dois resultados se juntam por RRF, que compara
    posicao em vez de pontuacao.

    O `score` do `ChunkHit` passa a ser a pontuacao da fusao, nao a do Lucene:
    ela so faz sentido comparada com os outros resultados da mesma consulta.
    """

    def __init__(
        self,
        driver: Driver,
        embedder: Embedder,
        fusion: ReciprocalRankFusion | None = None,
        database: str = "neo4j",
    ) -> None:
        self._driver = driver
        self._embedder = embedder
        self._fusion = fusion or ReciprocalRankFusion()
        self._database = database

    def search(self, query: str, limit: int = 10) -> list[ChunkHit]:
        words = _WORDS.findall(query)
        if not words or limit < 1:
            return []
        candidates = max(limit, _CANDIDATES)

        lexical = self._run(
            _LEXICAL, query=" ".join(f'"{word}"' for word in words), candidates=candidates
        )
        vector = self._run(
            _VECTOR, vector=list(self._embedder.embed_query(query)), candidates=candidates
        )

        rows = {**vector, **lexical}
        fused = self._fusion.fuse(list(lexical), list(vector))
        return [self._hit(rows[item.key], item.score) for item in fused[:limit]]

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

    def _run(self, cypher: str, **parameters: object) -> dict[str, dict]:
        """Roda uma das metades e devolve as linhas por chave, em ordem.

        O parametro se chama `cypher`, e nao `query`: a consulta lexical passa
        um parametro de nome `query` para o Cypher, e os dois nomes colidiam.
        """
        records, _, _ = self._driver.execute_query(
            cypher, database_=self._database, routing_="r", **parameters
        )
        return {row["key"]: dict(row) for row in records}

    @staticmethod
    def _hit(row: dict, score: float) -> ChunkHit:
        return ChunkHit(
            repo=row["repo"],
            path=row["path"],
            first_line=row["first_line"],
            last_line=row["last_line"],
            heading=row["heading"] or "",
            text=row["text"],
            score=score,
            document_title=row["title"],
            document_kind=row["kind"],
            ingested_at=row["ingested_at"].to_native(),
        )
