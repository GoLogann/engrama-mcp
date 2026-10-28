from dataclasses import dataclass

from engrama.domain.entities import Edge, Node


@dataclass(frozen=True, slots=True)
class RepositoryGraph:
    """Os nos e as arestas extraidos de um repo num commit.

    E o pedaco de grafo de um dono (ADR 0009): a escrita aposenta as arestas
    de extracao do dono que esta rodada nao reencontrou. A estrutura e a
    documentacao de um repo sao montadas por servicos diferentes e juntadas
    com `merged`, porque chegam do mesmo commit.
    """

    nodes: tuple[Node, ...] = ()
    edges: tuple[Edge, ...] = ()

    def merged(self, other: "RepositoryGraph") -> "RepositoryGraph":
        """Junta os dois pedacos, mantendo um no so por identidade (o primeiro)."""
        nodes = {node.ref: node for node in (*other.nodes, *self.nodes)}
        return RepositoryGraph(tuple(nodes.values()), self.edges + other.edges)
