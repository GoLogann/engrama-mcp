from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import datetime

from engrama.application.dto.structure_check import (
    CallFact,
    DataStoreFact,
    GroundTruth,
    RouteFact,
)
from engrama.domain.services import RepositoryGraph


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
    """Leitura das rotas, chamadas e bancos gravados, para conferir com o groundtruth."""

    @abstractmethod
    def routes(self) -> list[RouteFact]: ...

    @abstractmethod
    def calls(self) -> list[CallFact]: ...

    @abstractmethod
    def datastores(self) -> list[DataStoreFact]: ...


class GroundTruthSource(ABC):
    @abstractmethod
    def load(self) -> GroundTruth: ...
