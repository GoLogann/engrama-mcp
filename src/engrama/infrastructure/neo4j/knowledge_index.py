import re

from neo4j import Driver

from engrama.application.dto.knowledge import ChunkHit, IndexedDocument
from engrama.application.ports.knowledge import KnowledgeIndex

CHUNK_INDEX = "chunk_text"

# A consulta vai para o Lucene, que trata `/`, `?`, `:` e `-` como sintaxe. Em
# vez de escapar caractere por caractere, a pergunta e reduzida as palavras:
# e assim que o analisador quebra o texto indexado tambem, entao nao se perde
# nada, e nenhuma pontuacao da pergunta pode virar operador.
_WORDS = re.compile(r"\w+", re.UNICODE)

_SEARCH = f"""
CALL db.index.fulltext.queryNodes('{CHUNK_INDEX}', $query) YIELD node, score
MATCH (node)-[:PART_OF {{open: true}}]->(d)
WHERE d:Doc OR d:Decision
RETURN node.repo AS repo, node.path AS path, node.first_line AS first_line,
       node.last_line AS last_line, node.heading AS heading, node.text AS text,
       score AS score, d.title AS title, labels(d)[0] AS kind
ORDER BY score DESC, repo, path, first_line
LIMIT $limit
"""
# Documento com a aresta PART_OF aberta: o que vale hoje (ADR 0009). Um
# documento apagado do repo continua no grafo, com a aresta fechada, e nao
# aparece na busca. OPTIONAL porque documento vazio nao tem pedaco.
_DOCUMENTS = """
MATCH (d)-[:PART_OF {open: true}]->(:Repo)
WHERE d:Doc OR d:Decision
OPTIONAL MATCH (c:Chunk)-[:PART_OF {open: true}]->(d)
RETURN d.repo AS repo, d.path AS path, labels(d)[0] AS kind, d.title AS title,
       count(c) AS chunks
ORDER BY repo, path
"""


class Neo4jKnowledgeIndex(KnowledgeIndex):
    """Busca por texto no indice de texto completo do Neo4j.

    A parte vetorial da busca hibrida entra quando houver chave de embeddings:
    o resultado dos dois lados se junta por RRF, sem mudar esta porta.
    """

    def __init__(self, driver: Driver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    def search(self, query: str, limit: int = 10) -> list[ChunkHit]:
        terms = " ".join(_WORDS.findall(query))
        if not terms or limit < 1:
            return []
        records, _, _ = self._driver.execute_query(
            _SEARCH, query=terms, limit=limit, database_=self._database
        )
        return [
            ChunkHit(
                repo=row["repo"],
                path=row["path"],
                first_line=row["first_line"],
                last_line=row["last_line"],
                heading=row["heading"] or "",
                text=row["text"],
                score=row["score"],
                document_title=row["title"],
                document_kind=row["kind"],
            )
            for row in records
        ]

    def documents(self) -> list[IndexedDocument]:
        records, _, _ = self._driver.execute_query(_DOCUMENTS, database_=self._database)
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
