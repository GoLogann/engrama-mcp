from dataclasses import dataclass
from typing import ClassVar

from engrama.domain.entities.node import Node
from engrama.domain.errors import InvalidNode
from engrama.domain.value_objects import NodeKind


@dataclass(frozen=True, slots=True, eq=False)
class Concept(Node):
    """Conceito do dominio dos projetos (pista, dificuldade, canal...).

    `slug` e o nome canonico; `aliases` guarda as grafias que apontam para ele
    (`cue` e `pista`), para que a busca resolva qualquer uma.
    """

    node_kind: ClassVar[NodeKind] = NodeKind.CONCEPT

    slug: str
    name: str
    aliases: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return self.slug


@dataclass(frozen=True, slots=True, eq=False)
class Doc(Node):
    node_kind: ClassVar[NodeKind] = NodeKind.DOC

    repo: str
    path: str
    title: str

    @property
    def key(self) -> str:
        return f"{self.repo}:{self.path}"


@dataclass(frozen=True, slots=True, eq=False)
class Decision(Node):
    """Registro de decisao (ADR) escrito no repo, como `docs/decisoes/0001-*.md`."""

    node_kind: ClassVar[NodeKind] = NodeKind.DECISION

    repo: str
    path: str
    title: str
    status: str | None = None

    @property
    def key(self) -> str:
        return f"{self.repo}:{self.path}"


@dataclass(frozen=True, slots=True, eq=False)
class Chunk(Node):
    """Pedaco de um documento, com a faixa de linhas de onde saiu.

    A busca devolve chunks, nao documentos inteiros, porque a fonte que o MCP
    cita precisa apontar para o lugar do texto: as fontes das perguntas de
    ouro sao `repo/caminho:linha`. O texto e o que entra no indice, ja
    mascarado pela politica de segredos.
    """

    node_kind: ClassVar[NodeKind] = NodeKind.CHUNK

    repo: str
    path: str
    index: int
    text: str
    first_line: int
    last_line: int
    heading: str = ""

    def __post_init__(self) -> None:
        if self.index < 0:
            raise InvalidNode(f"indice de chunk invalido: {self.index}")
        if self.first_line < 1 or self.last_line < self.first_line:
            raise InvalidNode(
                f"faixa de linhas invalida em {self.path}: {self.first_line}-{self.last_line}"
            )
        if not self.text.strip():
            raise InvalidNode(f"chunk sem texto em {self.path}#{self.index}")

    @property
    def key(self) -> str:
        return f"{self.repo}:{self.path}#{self.index}"

    @property
    def source(self) -> str:
        """Como a fonte e citada: `repo/caminho:primeira_linha`."""
        return f"{self.repo}/{self.path}:{self.first_line}"


@dataclass(frozen=True, slots=True, eq=False)
class Issue(Node):
    """Issue do GitHub citada no codigo ou nos docs (`issue #7`)."""

    node_kind: ClassVar[NodeKind] = NodeKind.ISSUE

    repo: str
    number: int

    def __post_init__(self) -> None:
        if self.number < 1:
            raise InvalidNode(f"numero de issue invalido: {self.number}")

    @property
    def key(self) -> str:
        return f"{self.repo}#{self.number}"
