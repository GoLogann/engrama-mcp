from engrama.application.dto.knowledge import ChunkHit
from engrama.application.ports.knowledge import KnowledgeIndex


class SearchKnowledge:
    """Busca na camada de documentacao, devolvendo os pedacos com a fonte.

    E a mesma leitura que a tool `search_knowledge` do MCP vai expor: o
    handler so traduz a entrada e a saida.
    """

    def __init__(self, index: KnowledgeIndex) -> None:
        self._index = index

    def execute(self, query: str, limit: int = 10) -> list[ChunkHit]:
        if not query.strip():
            return []
        return self._index.search(query, limit)
