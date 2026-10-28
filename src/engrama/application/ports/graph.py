from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import datetime

from engrama.application.dto.consulta import (
    Connection,
    Direction,
    NodeSummary,
    ProjectOverview,
)
from engrama.application.dto.structure_check import (
    CallFact,
    DataStoreFact,
    GroundTruth,
    RouteFact,
)
from engrama.domain.entities import Endpoint
from engrama.domain.services import RepositoryGraph
from engrama.domain.value_objects import NodeRef


class GraphWriter(ABC):
    """Escrita da camada de estrutura. Usada so pela ingestao: o MCP nunca
    recebe esta porta (segregacao de interfaces)."""

    @abstractmethod
    def ensure_schema(self) -> None: ...

    @abstractmethod
    def write(self, graphs: Mapping[str, RepositoryGraph], run_id: str, at: datetime) -> None:
        """Grava o grafo de cada repo dono. Arestas de extracao de um dono que
        nao vieram nesta rodada deixam de valer em `at` (ganham `valid_to`)."""


class StructureReader(ABC):
    """Leitura da camada de estrutura gravada: para conferir com o groundtruth
    e para a documentacao saber quais endpoints existem."""

    @abstractmethod
    def routes(self) -> list[RouteFact]: ...

    @abstractmethod
    def calls(self) -> list[CallFact]: ...

    @abstractmethod
    def datastores(self) -> list[DataStoreFact]: ...

    @abstractmethod
    def endpoints(self) -> list[Endpoint]:
        """Os endpoints com aresta `EXPOSES` aberta, um por endpoint.

        A camada de documentacao so liga uma rota citada num texto a um
        endpoint que esta aqui: assim a aresta nunca aponta para um no que
        nao existe no grafo.
        """


class GraphReader(ABC):
    """Leitura do grafo para as tools do MCP.

    Separada do `GraphWriter` por construcao (segregacao de interfaces): um
    handler de tool recebe esta porta e nao tem como escrever no grafo, nem
    por engano. So le o que vale hoje — arestas com `open: true` (ADR 0009).
    """

    @abstractmethod
    def find(self, text: str, limit: int = 10) -> list[NodeSummary]:
        """Nos cujo nome, caminho ou rota casa com o texto, do mais para o
        menos parecido. Texto vazio devolve lista vazia."""

    @abstractmethod
    def node(self, ref: NodeRef) -> NodeSummary | None:
        """O no, ou `None` se ele nao existe no grafo."""

    @abstractmethod
    def edges(self, ref: NodeRef, direction: Direction) -> list[Connection]:
        """As arestas abertas em volta do no, com a evidencia de cada uma."""

    @abstractmethod
    def path(self, origin: NodeRef, target: NodeRef, max_depth: int = 6) -> list[Connection]:
        """O caminho mais curto entre dois nos, ou lista vazia se nao ha um
        dentro de `max_depth`. Nao achar caminho e resposta, nao erro."""

    @abstractmethod
    def overview(self, project: str) -> ProjectOverview | None:
        """O retrato estrutural de um projeto, ou `None` se ele nao existe."""


class GroundTruthSource(ABC):
    @abstractmethod
    def load(self) -> GroundTruth: ...
