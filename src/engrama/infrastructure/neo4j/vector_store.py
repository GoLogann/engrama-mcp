from collections.abc import Mapping

from neo4j import Driver

from engrama.application.ports.knowledge import Vector, VectorStore

# `MATCH`, nao `MERGE`: chave de pedaco que nao esta no grafo e ignorada, para
# um vetor solto nunca criar no. `setNodeVectorProperty` e o caminho que o
# Neo4j documenta para gravar vetor: guarda como vetor de verdade, e nao como
# lista de numeros, que e o que o indice vetorial espera ler.
_STORE = """
UNWIND $rows AS row
MATCH (c:Chunk {key: row.key})
CALL db.create.setNodeVectorProperty(c, 'embedding', row.vector)
RETURN count(c) AS stored
"""


class Neo4jVectorStore(VectorStore):
    def __init__(self, driver: Driver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    def store(self, vectors: Mapping[str, Vector]) -> int:
        if not vectors:
            return 0
        rows = [{"key": key, "vector": list(vector)} for key, vector in vectors.items()]
        records, _, _ = self._driver.execute_query(_STORE, rows=rows, database_=self._database)
        return records[0]["stored"] if records else 0
