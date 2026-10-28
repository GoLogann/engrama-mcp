from abc import ABC, abstractmethod

from engrama.application.dto.evaluation import GoldenQuestion
from engrama.application.dto.knowledge import ChunkHit, IndexedDocument


class KnowledgeIndex(ABC):
    """Busca na camada de documentacao. So leitura: quem escreve os pedacos e
    o `GraphWriter`, porque eles sao nos do grafo como qualquer outro."""

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[ChunkHit]:
        """Os pedacos mais parecidos com a pergunta, do mais para o menos.

        A busca da fase 2 e por texto. Quando houver embeddings, a parte
        vetorial entra aqui e o resultado se junta por RRF, sem mudar quem
        chama. Consulta vazia devolve lista vazia.
        """

    @abstractmethod
    def documents(self) -> list[IndexedDocument]:
        """Os documentos que o indice tem hoje, em ordem."""


class GoldenQuestionSource(ABC):
    @abstractmethod
    def load(self) -> tuple[GoldenQuestion, ...]: ...
