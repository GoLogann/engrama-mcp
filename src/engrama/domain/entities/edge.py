from dataclasses import dataclass
from enum import StrEnum

from engrama.domain.errors import InvalidEdge
from engrama.domain.value_objects import NodeKind, NodeRef, Provenance, Source, Validity

K = NodeKind


class EdgeKind(StrEnum):
    EXPOSES = "EXPOSES"
    CALLS = "CALLS"
    STORES_IN = "STORES_IN"
    PART_OF = "PART_OF"
    DOCUMENTED_IN = "DOCUMENTED_IN"
    MENTIONS_CONCEPT = "MENTIONS_CONCEPT"
    REFERENCES_ISSUE = "REFERENCES_ISSUE"
    ABOUT = "ABOUT"
    AUTHORED_BY = "AUTHORED_BY"
    SUPERSEDES = "SUPERSEDES"


@dataclass(frozen=True, slots=True)
class EdgeRule:
    pairs: frozenset[tuple[NodeKind, NodeKind]]
    origins: frozenset[Source]


def _rule(sources: set[NodeKind], targets: set[NodeKind], origins: set[Source]) -> EdgeRule:
    return EdgeRule(frozenset((s, t) for s in sources for t in targets), frozenset(origins))


_STRUCTURE = {Source.EXTRACTION}
_EXPERIENCE = {Source.PERSON, Source.DOCUMENT}
_EPISODE_SUBJECTS = {
    K.PROJECT,
    K.REPO,
    K.MODULE,
    K.ENDPOINT,
    K.DATASTORE,
    K.CONCEPT,
    K.DOC,
    K.DECISION,
    K.ISSUE,
}

# Quem pode ligar o que a quem, e com qual origem. As arestas estruturais so
# nascem da extracao deterministica (principio 1): o LLM nunca cria CALLS.
RULES: dict[EdgeKind, EdgeRule] = {
    EdgeKind.EXPOSES: _rule({K.MODULE}, {K.ENDPOINT}, _STRUCTURE),
    EdgeKind.CALLS: _rule({K.MODULE}, {K.ENDPOINT}, _STRUCTURE),
    EdgeKind.STORES_IN: _rule({K.REPO, K.MODULE}, {K.DATASTORE}, _STRUCTURE),
    EdgeKind.PART_OF: EdgeRule(
        frozenset(
            {
                (K.MODULE, K.MODULE),
                (K.MODULE, K.REPO),
                (K.REPO, K.PROJECT),
                (K.DATASTORE, K.REPO),
                (K.DOC, K.REPO),
                (K.DECISION, K.REPO),
            }
        ),
        frozenset(_STRUCTURE),
    ),
    EdgeKind.DOCUMENTED_IN: _rule(
        {K.PROJECT, K.REPO, K.MODULE, K.ENDPOINT, K.DATASTORE},
        {K.DOC, K.DECISION},
        {Source.EXTRACTION, Source.DOCUMENT, Source.LLM},
    ),
    EdgeKind.MENTIONS_CONCEPT: _rule(
        {K.DOC, K.DECISION, K.MODULE, K.ENDPOINT, K.ISSUE, K.EPISODE},
        {K.CONCEPT},
        {Source.DOCUMENT, Source.LLM, Source.PERSON},
    ),
    EdgeKind.REFERENCES_ISSUE: _rule(
        {K.MODULE, K.DOC, K.DECISION, K.EPISODE}, {K.ISSUE}, {Source.EXTRACTION, Source.PERSON}
    ),
    EdgeKind.ABOUT: _rule({K.EPISODE}, _EPISODE_SUBJECTS, _EXPERIENCE),
    EdgeKind.AUTHORED_BY: _rule({K.EPISODE}, {K.PERSON}, _EXPERIENCE),
    EdgeKind.SUPERSEDES: _rule({K.EPISODE}, {K.EPISODE}, _EXPERIENCE),
}


@dataclass(frozen=True, slots=True)
class Edge:
    """Aresta do grafo. Nao existe aresta sem proveniencia e validade no tempo."""

    kind: EdgeKind
    source: NodeRef
    target: NodeRef
    provenance: Provenance
    validity: Validity

    def __post_init__(self) -> None:
        rule = RULES[self.kind]
        if (self.source.kind, self.target.kind) not in rule.pairs:
            raise InvalidEdge(f"{self.kind} nao liga {self.source.kind} a {self.target.kind}")
        if self.provenance.source not in rule.origins:
            raise InvalidEdge(f"{self.kind} nao pode vir de {self.provenance.source}")
        if self.source == self.target:
            raise InvalidEdge(f"{self.kind} de um no para ele mesmo: {self.source}")

    def __str__(self) -> str:
        return f"{self.source} -[{self.kind}]-> {self.target}"
