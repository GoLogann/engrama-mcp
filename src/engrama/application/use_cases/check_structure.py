from engrama.application.dto.structure_check import StructureCheckReport
from engrama.application.ports.graph import GroundTruthSource, StructureReader


class CheckStructureAgainstGroundTruth:
    """Portao 1: o grafo gravado tem exatamente as rotas e chamadas conferidas a mao."""

    def __init__(self, reader: StructureReader, ground_truth: GroundTruthSource) -> None:
        self._reader = reader
        self._ground_truth = ground_truth

    def execute(self) -> StructureCheckReport:
        expected = self._ground_truth.load()
        routes = set(self._reader.routes())
        calls = set(self._reader.calls())
        return StructureCheckReport(
            expected_routes=len(expected.routes),
            expected_calls=len(expected.calls),
            missing_routes=tuple(sorted(expected.routes - routes)),
            unexpected_routes=tuple(sorted(routes - expected.routes)),
            missing_calls=tuple(sorted(expected.calls - calls)),
            unexpected_calls=tuple(sorted(calls - expected.calls)),
        )
