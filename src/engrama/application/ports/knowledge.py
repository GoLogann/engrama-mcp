from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence

from engrama.application.dto.evaluation import GoldenQuestion
from engrama.application.dto.knowledge import ChunkHit, IndexedDocument

Vector = tuple[float, ...]

# Os valores que `KnowledgeIndex.ranking()` pode devolver. Ficam na porta, e
# nao no adapter, porque fazem parte do contrato: quem le o relatorio precisa
# do mesmo vocabulario, seja o indice do Neo4j ou um fake.
BY_VECTOR = "vetor"
BY_WORD = "palavra"
# Uma rodada em que a busca degradou no meio: parte das consultas foi por
# vetor e parte pela reserva. Dizer so `palavra` jogaria fora o que as
# primeiras acharam; dizer so `vetor` esconderia a degradacao.
BY_MIXED = "misto"


class EmbeddingUnavailable(Exception):
    """O provedor de embeddings nao respondeu e nao vai responder agora.

    Existe para a busca nao precisar conhecer o provedor: quem implementa a
    porta traduz o erro dele (teto de taxa esgotado, servico fora) para isto.
    Erro de configuracao — chave errada, modelo inexistente — nao e isto, e
    deve subir como veio, porque a saida e consertar, nao responder pior.
    """


class Embedder(ABC):
    """Transforma texto em vetor, para a metade vetorial da busca.

    Documento e pergunta sao embutidos por caminhos diferentes de proposito:
    os modelos de recuperacao esperam saber se o texto e o que se guarda ou o
    que se procura, e usar o mesmo caminho para os dois piora o resultado.
    """

    @abstractmethod
    def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        """Um vetor por texto, na mesma ordem. Lista vazia devolve vazia."""

    @abstractmethod
    def embed_query(self, text: str) -> Vector:
        """O vetor de uma pergunta."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Quantos numeros tem cada vetor. O indice vetorial e criado com
        esse tamanho, entao trocar de modelo para outro tamanho exige
        recriar o indice."""


class VectorStore(ABC):
    """Escreve os vetores dos pedacos ja gravados no grafo.

    Porta separada do `GraphWriter` porque o vetor nao e um fato do dominio:
    e artefato de recuperacao, derivado do texto do pedaco. A entidade
    `Chunk` nao o carrega, e nenhum caso de uso de leitura o ve.
    """

    @abstractmethod
    def store(self, vectors: Mapping[str, Vector]) -> int:
        """Grava os vetores, por chave de pedaco, e devolve quantos gravou.

        Chave que nao existe no grafo e ignorada, nao cria no.
        """


class KnowledgeIndex(ABC):
    """Busca na camada de documentacao. So leitura: quem escreve os pedacos e
    o `GraphWriter`, porque eles sao nos do grafo como qualquer outro."""

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[ChunkHit]:
        """Os pedacos mais parecidos com a pergunta, do mais para o menos.

        O ranking e por significado quando ha embeddings, e por palavra
        quando nao ha (ADR 0011). Consulta vazia devolve lista vazia.
        """

    @abstractmethod
    def ranking(self) -> str:
        """Como esta busca ordena hoje: `vetor` ou `palavra`.

        Faz parte do contrato porque a reserva por palavra responde pior, e
        um relatorio que nao diz qual motor respondeu afirma um numero sobre
        o outro. Medicao sem essa informacao nao e medicao.
        """

    @abstractmethod
    def documents(self) -> list[IndexedDocument]:
        """Os documentos que o indice tem hoje, em ordem."""


class GoldenQuestionSource(ABC):
    @abstractmethod
    def load(self) -> tuple[GoldenQuestion, ...]: ...
