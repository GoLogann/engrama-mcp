from dataclasses import dataclass

from engrama.domain.value_objects.http_route import HttpRoute
from engrama.domain.value_objects.provenance import Evidence

# Fatos que a extracao deterministica encontra no codigo. Ainda nao sao nos
# nem arestas: o StructuralGraphBuilder os transforma no grafo. `module` e o
# diretorio do arquivo relativo a raiz do repo ("." para a raiz).


@dataclass(frozen=True, slots=True)
class DeclaredRoute:
    """Rota HTTP que um repo expoe."""

    repo: str
    module: str
    route: HttpRoute
    evidence: Evidence
    handler: str | None = None


@dataclass(frozen=True, slots=True)
class CallSite:
    """Chamada HTTP que um repo faz, com a rota na forma canonica."""

    repo: str
    module: str
    route: HttpRoute
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class DataStoreUse:
    """Banco que um repo usa, como declarado na infraestrutura (compose)."""

    repo: str
    kind: str
    name: str
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class IssueReference:
    """Citacao a uma issue do GitHub encontrada no codigo (`issue #7`)."""

    repo: str
    module: str
    issue_repo: str
    number: int
    evidence: Evidence
