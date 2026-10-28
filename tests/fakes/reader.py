"""Leitor de grafo em memoria, para os casos de uso de consulta.

Guarda nos e arestas como listas e responde as mesmas perguntas que o adapter
do Neo4j responde. Nao imita o Cypher: a busca de `find` e por substring e o
caminho e uma largura simples. O que o contrato cobra dos dois esta em
`tests/contracts/`.
"""

from collections import deque

from engrama.application.dto.consulta import (
    Connection,
    Direction,
    NodeSummary,
    ProjectOverview,
)
from engrama.application.ports.graph import GraphReader
from engrama.domain.value_objects import NodeKind, NodeRef


class InMemoryReader(GraphReader):
    def __init__(
        self,
        nodes: list[NodeSummary] | None = None,
        edges: list[Connection] | None = None,
    ) -> None:
        self.nodes = nodes or []
        self.edges_ = edges or []

    def find(self, text: str, limit: int = 10) -> list[NodeSummary]:
        wanted = text.strip().casefold()
        if not wanted:
            return []
        hits = [
            node
            for node in self.nodes
            if wanted in node.key.casefold() or wanted in node.label.casefold()
        ]
        # Exato primeiro, para o fake nao desempatar diferente do Neo4j, que
        # ordena por tamanho do rotulo.
        hits.sort(key=lambda node: (node.label.casefold() != wanted, len(node.label), node.key))
        return hits[:limit]

    def node(self, ref: NodeRef) -> NodeSummary | None:
        return next((node for node in self.nodes if node.ref == ref), None)

    def edges(self, ref: NodeRef, direction: Direction) -> list[Connection]:
        chega = direction in (Direction.IN, Direction.BOTH)
        sai = direction in (Direction.OUT, Direction.BOTH)
        return [
            edge
            for edge in self.edges_
            if (chega and edge.target.ref == ref) or (sai and edge.origin.ref == ref)
        ]

    def path(self, origin: NodeRef, target: NodeRef, max_depth: int = 6) -> list[Connection]:
        """Largura primeiro, ignorando o sentido da aresta: "como se conectam"
        nao e "o que chama o que"."""
        queue: deque[tuple[NodeRef, list[Connection]]] = deque([(origin, [])])
        seen = {origin}
        while queue:
            current, walked = queue.popleft()
            if current == target:
                return walked
            if len(walked) >= max_depth:
                continue
            for edge in self.edges_:
                for near, far in ((edge.origin, edge.target), (edge.target, edge.origin)):
                    if near.ref == current and far.ref not in seen:
                        seen.add(far.ref)
                        queue.append((far.ref, [*walked, edge]))
        return []

    def overview(self, project: str) -> ProjectOverview | None:
        node = next(
            (
                one
                for one in self.nodes
                if one.ref.kind is NodeKind.PROJECT and one.ref.key == project
            ),
            None,
        )
        if node is None:
            return None
        repos = [one for one in self.nodes if one.ref.kind is NodeKind.REPO]
        return ProjectOverview(
            project=project,
            repos=tuple(repos),
            modules=sum(1 for one in self.nodes if one.ref.kind is NodeKind.MODULE),
            endpoints=sum(1 for one in self.nodes if one.ref.kind is NodeKind.ENDPOINT),
            datastores=tuple(one for one in self.nodes if one.ref.kind is NodeKind.DATASTORE),
            documents=sum(1 for one in self.nodes if one.ref.kind is NodeKind.DOC),
        )
