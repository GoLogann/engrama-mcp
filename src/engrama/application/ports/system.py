from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime:
        """Instante atual, com fuso horario."""


@dataclass(frozen=True, slots=True)
class SecretFinding:
    rule: str
    line: int


@dataclass(frozen=True, slots=True)
class Redaction:
    text: str
    findings: tuple[SecretFinding, ...]


class SecretScanner(ABC):
    """Politica de segredos de docs/seguranca.md: o que nunca e lido e o que
    e mascarado no texto que entra no grafo ou sai pelo MCP."""

    @abstractmethod
    def excludes(self, path: str) -> bool: ...

    @abstractmethod
    def redact(self, text: str) -> Redaction: ...
