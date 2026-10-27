from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from engrama.application.dto.ingestion import RepositoryFacts
from engrama.domain.entities import Edge
from engrama.domain.services import CallRouteMatcher, MatchReport, StructuralGraphBuilder
from engrama.domain.value_objects import Validity


@dataclass(frozen=True, slots=True)
class LinkResult:
    report: MatchReport
    edges_by_caller: Mapping[str, tuple[Edge, ...]]


class LinkCallsToRoutes:
    """Casa as chamadas de todos os repos com as rotas de todos os repos e
    gera as arestas CALLS, cada uma pertencendo ao repo que faz a chamada."""

    def __init__(self, builder: StructuralGraphBuilder) -> None:
        self._builder = builder

    def execute(
        self,
        repositories: Sequence[RepositoryFacts],
        consumes: Mapping[str, Sequence[str]],
        at: datetime,
    ) -> LinkResult:
        calls = [call for r in repositories for call in r.facts.calls]
        routes = [route for r in repositories for route in r.facts.routes]
        report = CallRouteMatcher(consumes).match(calls, routes)

        committed_at = {r.spec.repo.name: r.committed_at for r in repositories}
        by_caller = defaultdict(list)
        for match in report.matches:
            by_caller[match.call.repo].append(match)
        edges = {
            caller: self._builder.calls(
                matches, Validity.starting(committed_at[caller], ingested_at=at)
            )
            for caller, matches in by_caller.items()
        }
        return LinkResult(report=report, edges_by_caller=edges)
