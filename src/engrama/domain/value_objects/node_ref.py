from dataclasses import dataclass
from enum import StrEnum

from engrama.domain.errors import InvalidNode


class NodeKind(StrEnum):
    """Familias de no do grafo. O valor e o rotulo usado no banco."""

    PROJECT = "Project"
    REPO = "Repo"
    MODULE = "Module"
    ENDPOINT = "Endpoint"
    DATASTORE = "DataStore"
    CONCEPT = "Concept"
    DOC = "Doc"
    DECISION = "Decision"
    CHUNK = "Chunk"
    ISSUE = "Issue"
    EPISODE = "Episode"
    PERSON = "Person"


@dataclass(frozen=True, slots=True)
class NodeRef:
    """Identidade de um no: familia + chave natural (formato em docs/ontologia.md)."""

    kind: NodeKind
    key: str

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise InvalidNode(f"chave vazia para {self.kind}")

    def __str__(self) -> str:
        return f"{self.kind}({self.key})"
