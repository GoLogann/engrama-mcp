from dataclasses import dataclass


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
    ouro: `repo/caminho:linha`.
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

    @property
    def source(self) -> str:
        return f"{self.repo}/{self.path}:{self.first_line}"

    @property
    def file(self) -> str:
        return f"{self.repo}/{self.path}"

    def covers(self, line: int) -> bool:
        return self.first_line <= line <= self.last_line
