"""DTOs das tools de leitura do MCP.

Toda saida daqui carrega fonte: arquivo e linha, documento, ou episodio com
autor e data. E a regra 1 do servidor (docs/fundamentacao.md) e tambem o que
a avaliacao cobra no Portao 2 — resposta sem fonte conta como errada.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from engrama.domain.value_objects import NodeRef


class Direction(StrEnum):
    """De que lado do no olhar.

    `IN` responde "quem usa isto": as arestas que chegam. `OUT` responde "do
    que isto depende": as que saem. `BOTH` e o impacto de mudar o no, que
    precisa dos dois lados.
    """

    IN = "entrada"
    OUT = "saida"
    BOTH = "ambos"


@dataclass(frozen=True, slots=True)
class NodeSummary:
    """Um no do grafo, pronto para ser citado numa resposta."""

    ref: NodeRef
    label: str
    repo: str = ""
    # Onde o no foi visto no codigo, quando a familia tem isso (um `Endpoint`
    # tem handler e linha; um `Project` nao tem arquivo nenhum).
    source: str = ""

    @property
    def kind(self) -> str:
        return self.ref.kind.value

    @property
    def key(self) -> str:
        return self.ref.key


@dataclass(frozen=True, slots=True)
class Connection:
    """Uma aresta com a evidencia que a sustenta.

    `evidence` sao as fontes no formato `repo/caminho:linha`. Uma `CALLS`
    carrega a evidencia dos dois lados — quem chama e quem expoe — e por isso
    a lista tem mais de um item com frequencia.
    """

    origin: NodeSummary
    target: NodeSummary
    kind: str
    evidence: tuple[str, ...] = ()
    source: str = ""
    confidence: str = ""
    ingested_at: datetime | None = None

    def __str__(self) -> str:
        return f"{self.origin.label} -{self.kind}-> {self.target.label}"


@dataclass(frozen=True, slots=True)
class Resolution:
    """O resultado de transformar um texto num no do grafo.

    As tools recebem texto ("o endpoint de ranking"), nao identidade. Tres
    saidas possiveis, e as tres sao resposta: achou um; achou varios e nao da
    para escolher; nao achou nenhum. Escolher sozinho entre varios seria
    adivinhar, que e o que o casamento de rotas do ADR 0010 ja recusa.
    """

    query: str
    node: NodeSummary | None = None
    candidates: tuple[NodeSummary, ...] = ()

    @property
    def found(self) -> bool:
        return self.node is not None

    @property
    def ambiguous(self) -> bool:
        return self.node is None and len(self.candidates) > 1

    @property
    def missing(self) -> bool:
        return self.node is None and not self.candidates


@dataclass(frozen=True, slots=True)
class UsageReport:
    """Quem usa um no, e do que ele depende."""

    node: NodeSummary
    incoming: tuple[Connection, ...] = ()
    outgoing: tuple[Connection, ...] = ()

    @property
    def total(self) -> int:
        return len(self.incoming) + len(self.outgoing)

    @property
    def repos_affected(self) -> tuple[str, ...]:
        repos = {
            summary.repo
            for edge in self.incoming + self.outgoing
            for summary in (edge.origin, edge.target)
            if summary.repo and summary.repo != self.node.repo
        }
        return tuple(sorted(repos))


@dataclass(frozen=True, slots=True)
class ConnectionPath:
    """O caminho entre dois nos, aresta a aresta.

    Vazio quer dizer que nao ha caminho dentro da profundidade pedida, o que
    e resposta legitima: dois repos sem relacao nao se conectam.
    """

    origin: NodeSummary
    target: NodeSummary
    steps: tuple[Connection, ...] = ()

    @property
    def found(self) -> bool:
        return bool(self.steps)

    @property
    def length(self) -> int:
        return len(self.steps)


@dataclass(frozen=True, slots=True)
class ProjectOverview:
    """Retrato de um projeto pela estrutura que foi extraida.

    Sem os resumos por LLM (Fase 2), `summary` fica vazio e o retrato e so o
    que a extracao determinou. O relatorio diz isso em vez de fingir que o
    projeto nao tem resumo nenhum.
    """

    project: str
    repos: tuple[NodeSummary, ...] = ()
    modules: int = 0
    endpoints: int = 0
    datastores: tuple[NodeSummary, ...] = ()
    documents: int = 0
    summary: str = ""
    readmes: tuple[NodeSummary, ...] = field(default_factory=tuple)

    @property
    def has_summary(self) -> bool:
        return bool(self.summary.strip())
