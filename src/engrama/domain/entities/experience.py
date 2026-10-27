from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import ClassVar

from engrama.domain.entities.edge import Edge, EdgeKind
from engrama.domain.entities.node import Node
from engrama.domain.errors import EpisodeAlreadySuperseded, InvalidEpisode
from engrama.domain.value_objects import NodeKind, NodeRef, Provenance, Source, Validity


@dataclass(frozen=True, slots=True, eq=False)
class Person(Node):
    node_kind: ClassVar[NodeKind] = NodeKind.PERSON

    login: str
    name: str | None = None

    @property
    def key(self) -> str:
        return self.login


class EpisodeType(StrEnum):
    """Os valores seguem o campo `tipo` do formato de episodio do doc."""

    LEARNING = "aprendizado"
    DECISION = "decisao"
    PROBLEM = "problema"
    REFLECTION = "reflexao"


@dataclass(frozen=True, slots=True, eq=False)
class Episode(Node):
    """O que o time aprendeu, decidiu, enfrentou ou refletiu, com autor e data.

    Um episodio nunca e editado. Quando deixa de valer, `supersede` devolve
    esta versao encerrada (`valid_to` preenchido) e um sucessor que aponta para
    ela por `SUPERSEDES` (RASMUSSEN et al., 2025).
    """

    node_kind: ClassVar[NodeKind] = NodeKind.EPISODE

    id: str
    episode_type: EpisodeType
    text: str
    about: tuple[NodeRef, ...]
    author: NodeRef
    validity: Validity
    provenance: Provenance
    supersedes: str | None = None

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise InvalidEpisode("episodio sem texto")
        if not self.about:
            raise InvalidEpisode("episodio precisa estar ligado a pelo menos um no")
        if any(ref.kind in (NodeKind.EPISODE, NodeKind.PERSON) for ref in self.about):
            raise InvalidEpisode("episodio fala de codigo, docs ou conceitos, nao de episodios")
        if self.author.kind is not NodeKind.PERSON:
            raise InvalidEpisode(f"autor precisa ser uma pessoa, nao {self.author.kind}")
        if self.supersedes == self.id:
            raise InvalidEpisode("episodio nao substitui a si mesmo")
        if self.provenance.source not in (Source.PERSON, Source.DOCUMENT):
            raise InvalidEpisode(
                f"origem {self.provenance.source} nao cria episodio: so pessoa ou documento"
            )

    @property
    def key(self) -> str:
        return self.id

    @property
    def is_current(self) -> bool:
        return self.validity.is_open

    @classmethod
    def record(
        cls,
        *,
        id: str,
        episode_type: EpisodeType,
        text: str,
        about: tuple[NodeRef, ...],
        author: NodeRef,
        at: datetime,
        provenance: Provenance | None = None,
        valid_from: datetime | None = None,
        supersedes: str | None = None,
    ) -> "Episode":
        """Registra um episodio novo. `valid_from` permite semear um aprendizado
        antigo (de um doc de 2026-01) com a data em que ele passou a valer."""
        return cls(
            id=id,
            episode_type=episode_type,
            text=text,
            about=about,
            author=author,
            validity=Validity.starting(valid_from or at, ingested_at=at),
            provenance=provenance or Provenance.stated_by_person(),
            supersedes=supersedes,
        )

    def supersede(
        self,
        *,
        successor_id: str,
        text: str,
        author: NodeRef,
        at: datetime,
        episode_type: EpisodeType | None = None,
        about: tuple[NodeRef, ...] | None = None,
    ) -> tuple["Episode", "Episode"]:
        if not self.is_current:
            raise EpisodeAlreadySuperseded(f"episodio {self.id} ja foi substituido")
        closed = replace(self, validity=self.validity.closed_at(at))
        successor = Episode.record(
            id=successor_id,
            episode_type=episode_type or self.episode_type,
            text=text,
            about=about or self.about,
            author=author,
            at=at,
            supersedes=self.id,
        )
        return closed, successor

    def edges(self) -> tuple[Edge, ...]:
        """Arestas que o episodio cria: ABOUT, AUTHORED_BY e, se houver, SUPERSEDES."""

        def edge(kind: EdgeKind, target: NodeRef) -> Edge:
            return Edge(kind, self.ref, target, self.provenance, self.validity)

        edges = [edge(EdgeKind.ABOUT, ref) for ref in self.about]
        edges.append(edge(EdgeKind.AUTHORED_BY, self.author))
        if self.supersedes:
            edges.append(edge(EdgeKind.SUPERSEDES, NodeRef(NodeKind.EPISODE, self.supersedes)))
        return tuple(edges)
