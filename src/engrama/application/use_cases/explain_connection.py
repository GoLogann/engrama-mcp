from engrama.application.dto.consulta import ConnectionPath, Resolution
from engrama.application.ports.graph import GraphReader
from engrama.application.use_cases.resolve_node import ResolveNode


class ExplainConnection:
    """Como dois nos se ligam (tool `how_it_connects`).

    Devolve o caminho mais curto com a evidencia de cada aresta, que e o que
    permite a resposta citar fonte em vez de afirmar a ligacao. Nao achar
    caminho e resposta legitima: dois repos sem relacao nao se conectam, e
    dizer isso vale mais do que inventar um caminho longo e irrelevante.
    """

    def __init__(self, reader: GraphReader, resolve: ResolveNode) -> None:
        self._reader = reader
        self._resolve = resolve

    def execute(
        self, origin_text: str, target_text: str, max_depth: int = 6
    ) -> tuple[Resolution, Resolution, ConnectionPath | None]:
        origin = self._resolve.execute(origin_text)
        target = self._resolve.execute(target_text)
        if origin.node is None or target.node is None:
            return origin, target, None

        steps = self._reader.path(origin.node.ref, target.node.ref, max_depth)
        return (
            origin,
            target,
            ConnectionPath(origin=origin.node, target=target.node, steps=tuple(steps)),
        )
