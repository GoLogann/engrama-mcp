from pathlib import Path

import yaml

from engrama.application.dto.structure_check import CallFact, GroundTruth, RouteFact
from engrama.application.ports.graph import GroundTruthSource
from engrama.domain.value_objects import HttpMethod, HttpRoute


def _shape(route: str) -> str:
    method, path = route.split(" ", 1)
    return HttpRoute(HttpMethod(method), path).shape


class YamlGroundTruthSource(GroundTruthSource):
    """Le eval/structure_groundtruth.yaml (formato descrito no proprio arquivo)."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> GroundTruth:
        data = yaml.safe_load(self._path.read_text())
        routes = frozenset(
            RouteFact(repo, path, item["line"], item["route"])
            for repo, files in data["endpoints"].items()
            for path, items in files.items()
            for item in items
        )
        consumes = data["consumes"]
        calls = frozenset(
            CallFact(repo, path, item["line"], _shape(item["route"]), target)
            for repo, files in data["calls"].items()
            for path, items in files.items()
            for item in items
            for target in consumes[repo]
        )
        return GroundTruth(routes=routes, calls=calls)
