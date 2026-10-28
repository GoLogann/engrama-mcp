from engrama.application.dto.consulta import Direction, Resolution, UsageReport
from engrama.application.ports.graph import GraphReader
from engrama.application.use_cases.resolve_node import ResolveNode


class FindUsages:
    """Quem usa um no (tool `who_uses`).

    So as arestas que chegam: quem chama a rota, quem guarda no banco, que
    documento descreve o endpoint. O que o no usa fica para `AnalyzeImpact`,
    que olha os dois lados.
    """

    def __init__(self, reader: GraphReader, resolve: ResolveNode) -> None:
        self._reader = reader
        self._resolve = resolve

    def execute(self, text: str) -> tuple[Resolution, UsageReport | None]:
        resolution = self._resolve.execute(text)
        if resolution.node is None:
            return resolution, None
        incoming = self._reader.edges(resolution.node.ref, Direction.IN)
        return resolution, UsageReport(node=resolution.node, incoming=tuple(incoming))


class AnalyzeImpact:
    """O que muda se este no mudar (tool `impact_of_change`).

    Os dois lados, porque impacto e isso: quem depende do no quebra se ele
    mudar, e do que ele depende explica por que ele mudaria. O relatorio
    destaca os repos de fora, que sao onde a mudanca atravessa fronteira e
    deixa de ser problema de um time so.
    """

    def __init__(self, reader: GraphReader, resolve: ResolveNode) -> None:
        self._reader = reader
        self._resolve = resolve

    def execute(self, text: str) -> tuple[Resolution, UsageReport | None]:
        resolution = self._resolve.execute(text)
        if resolution.node is None:
            return resolution, None
        return resolution, UsageReport(
            node=resolution.node,
            incoming=tuple(self._reader.edges(resolution.node.ref, Direction.IN)),
            outgoing=tuple(self._reader.edges(resolution.node.ref, Direction.OUT)),
        )
