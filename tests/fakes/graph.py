from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime

from engrama.application.dto.structure_check import CallFact, DataStoreFact, RouteFact
from engrama.application.ports.graph import GraphWriter, StructureReader
from engrama.domain.entities import DataStore, Edge, EdgeKind, Endpoint, Node
from engrama.domain.services import RepositoryGraph


@dataclass
class StoredEdge:
    edge: Edge
    owner: str
    run_id: str
    open: bool = True
    valid_to: datetime | None = None


class InMemoryGraph(GraphWriter, StructureReader):
    """Grafo em memoria com a mesma semantica do Neo4j: upsert por chave,
    uma aresta aberta por (tipo, origem, destino) e aposentadoria por dono."""

    def __init__(self) -> None:
        self.nodes: dict[tuple[str, str], Node] = {}
        self.edges: list[StoredEdge] = []
        self.schema_ready = False

    def ensure_schema(self) -> None:
        self.schema_ready = True

    def write(self, graphs: Mapping[str, RepositoryGraph], run_id: str, at: datetime) -> None:
        for graph in graphs.values():
            for node in graph.nodes:
                self.nodes[(node.node_kind.value, node.key)] = node
        for owner, graph in graphs.items():
            for edge in graph.edges:
                current = self._open(edge)
                if current is None:
                    self.edges.append(StoredEdge(edge, owner, run_id))
                else:
                    # Como no Neo4j: valid_from e ingested_at so valem na criacao.
                    first = current.edge.validity
                    validity = replace(
                        edge.validity, valid_from=first.valid_from, ingested_at=first.ingested_at
                    )
                    current.edge = replace(edge, validity=validity)
                    current.owner, current.run_id = owner, run_id
        for stored in self.edges:
            if stored.owner in graphs and stored.open and stored.run_id != run_id:
                stored.open, stored.valid_to = False, at
        self._close_orphan_calls(at)

    def routes(self) -> list[RouteFact]:
        return [
            RouteFact(endpoint.repo, e.path, e.line, str(endpoint.route))
            for stored, endpoint in self._open_to_endpoints(EdgeKind.EXPOSES)
            for e in stored.edge.provenance.evidence
        ]

    def calls(self) -> list[CallFact]:
        facts = []
        for stored, endpoint in self._open_to_endpoints(EdgeKind.CALLS):
            caller = stored.edge.source.key.split(":", 1)[0]
            for e in stored.edge.provenance.evidence:
                if e.repo == caller:
                    facts.append(
                        CallFact(caller, e.path, e.line, endpoint.route.shape, endpoint.repo)
                    )
        return facts

    def endpoints(self) -> list[Endpoint]:
        found = {
            endpoint.key: endpoint for _, endpoint in self._open_to_endpoints(EdgeKind.EXPOSES)
        }
        return [found[key] for key in sorted(found)]

    def datastores(self) -> list[DataStoreFact]:
        facts = []
        for stored in self.open_edges(EdgeKind.STORES_IN):
            store = self.nodes[(stored.edge.target.kind.value, stored.edge.target.key)]
            assert isinstance(store, DataStore)
            facts.append(DataStoreFact(store.repo, store.store_kind.value, store.name))
        return facts

    def open_edges(self, kind: EdgeKind) -> list[StoredEdge]:
        return [s for s in self.edges if s.open and s.edge.kind is kind]

    def _close_orphan_calls(self, at: datetime) -> None:
        exposed = {s.edge.target for s in self.open_edges(EdgeKind.EXPOSES)}
        for stored in self.open_edges(EdgeKind.CALLS):
            if stored.edge.target not in exposed:
                stored.open, stored.valid_to = False, at

    def _open(self, edge: Edge) -> StoredEdge | None:
        return next(
            (
                s
                for s in self.edges
                if s.open
                and (s.edge.kind, s.edge.source, s.edge.target)
                == (edge.kind, edge.source, edge.target)
            ),
            None,
        )

    def _open_to_endpoints(self, kind: EdgeKind) -> list[tuple[StoredEdge, Endpoint]]:
        result = []
        for stored in self.open_edges(kind):
            endpoint = self.nodes[(stored.edge.target.kind.value, stored.edge.target.key)]
            assert isinstance(endpoint, Endpoint)
            result.append((stored, endpoint))
        return result
