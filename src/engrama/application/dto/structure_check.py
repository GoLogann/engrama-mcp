from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class RouteFact:
    """Rota exposta, como o groundtruth ou o grafo a descrevem."""

    repo: str
    path: str
    line: int
    route: str


@dataclass(frozen=True, slots=True, order=True)
class CallFact:
    """Chamada de `repo` (no arquivo e linha) para `target`. `shape` e a rota
    sem nomes de parametro, porque cliente e servidor nomeiam diferente."""

    repo: str
    path: str
    line: int
    shape: str
    target: str


@dataclass(frozen=True, slots=True, order=True)
class DataStoreFact:
    """Banco que um repo usa. Para o Qdrant, `name` e a colecao."""

    repo: str
    kind: str
    name: str


@dataclass(frozen=True, slots=True)
class GroundTruth:
    routes: frozenset[RouteFact]
    calls: frozenset[CallFact]
    datastores: frozenset[DataStoreFact] = frozenset()


@dataclass(frozen=True, slots=True)
class StructureCheckReport:
    expected_routes: int
    expected_calls: int
    missing_routes: tuple[RouteFact, ...]
    unexpected_routes: tuple[RouteFact, ...]
    missing_calls: tuple[CallFact, ...]
    unexpected_calls: tuple[CallFact, ...]
    expected_datastores: int = 0
    missing_datastores: tuple[DataStoreFact, ...] = ()
    unexpected_datastores: tuple[DataStoreFact, ...] = ()

    @property
    def passed(self) -> bool:
        return not (
            self.missing_routes
            or self.unexpected_routes
            or self.missing_calls
            or self.unexpected_calls
            or self.missing_datastores
            or self.unexpected_datastores
        )

    @property
    def route_coverage(self) -> float:
        return 1 - len(self.missing_routes) / self.expected_routes if self.expected_routes else 1.0

    @property
    def call_coverage(self) -> float:
        return 1 - len(self.missing_calls) / self.expected_calls if self.expected_calls else 1.0

    @property
    def datastore_coverage(self) -> float:
        missing = len(self.missing_datastores)
        return 1 - missing / self.expected_datastores if self.expected_datastores else 1.0
