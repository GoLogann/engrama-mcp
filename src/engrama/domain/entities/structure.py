from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from engrama.domain.entities.node import Node
from engrama.domain.errors import InvalidNode
from engrama.domain.value_objects import HttpRoute, NodeKind


class Stack(StrEnum):
    PYTHON_FASTAPI = "python-fastapi"
    TYPESCRIPT_REACT = "typescript-react"
    GO_GIN = "go-gin"
    DART_FLUTTER = "dart-flutter"


class DataStoreKind(StrEnum):
    POSTGRES = "postgres"
    QDRANT = "qdrant"
    REDIS = "redis"


@dataclass(frozen=True, slots=True, eq=False)
class Project(Node):
    node_kind: ClassVar[NodeKind] = NodeKind.PROJECT

    slug: str
    name: str

    @property
    def key(self) -> str:
        return self.slug


@dataclass(frozen=True, slots=True, eq=False)
class Repo(Node):
    node_kind: ClassVar[NodeKind] = NodeKind.REPO

    name: str
    project: str
    url: str
    commit: str
    stack: Stack

    @property
    def key(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True, eq=False)
class Module(Node):
    """Diretorio de codigo-fonte de um repo (ex.: `app/domain/services`).

    A granularidade e o pacote, nao o arquivo: e o nivel em que resumos fazem
    sentido. O arquivo e a linha exatos ficam na evidencia de cada aresta.
    """

    node_kind: ClassVar[NodeKind] = NodeKind.MODULE

    repo: str
    path: str

    def __post_init__(self) -> None:
        if self.path.startswith("/") or self.path.endswith("/"):
            raise InvalidNode(f"caminho de modulo deve ser relativo e sem barra final: {self.path}")

    @property
    def key(self) -> str:
        return f"{self.repo}:{self.path}"


@dataclass(frozen=True, slots=True, eq=False)
class Endpoint(Node):
    node_kind: ClassVar[NodeKind] = NodeKind.ENDPOINT

    repo: str
    route: HttpRoute
    handler: str | None = None

    @property
    def key(self) -> str:
        return f"{self.repo}:{self.route}"


@dataclass(frozen=True, slots=True, eq=False)
class DataStore(Node):
    node_kind: ClassVar[NodeKind] = NodeKind.DATASTORE

    repo: str
    store_kind: DataStoreKind
    name: str

    @property
    def key(self) -> str:
        return f"{self.repo}:{self.store_kind}:{self.name}"
