from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True, order=True)
class IndexedDocument:
    """Documento presente no indice, com quantos pedacos ele tem."""

    repo: str
    path: str
    kind: str
    title: str
    chunks: int


@dataclass(frozen=True, slots=True)
class ChunkHit:
    """Pedaco de documento devolvido pela busca, com de onde ele saiu.

    `source` e o que o MCP cita, no mesmo formato das fontes das perguntas de
    ouro: `repo/caminho:linha`. `ingested_at` e quando o grafo soube deste
    pedaco, que toda resposta de tool precisa devolver junto da fonte.
    """

    repo: str
    path: str
    first_line: int
    last_line: int
    heading: str
    text: str
    score: float
    document_title: str
    document_kind: str
    ingested_at: datetime

    @property
    def source(self) -> str:
        return f"{self.repo}/{self.path}:{self.first_line}"

    @property
    def file(self) -> str:
        return f"{self.repo}/{self.path}"

    def covers(self, line: int) -> bool:
        return self.first_line <= line <= self.last_line
