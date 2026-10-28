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
    # Pares cliente -> servidor que o codigo mostra e o catalogo nao declara.
    undeclared: tuple[tuple[str, str], ...] = ()


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
        return LinkResult(
            report=report,
            edges_by_caller=edges,
            undeclared=self._undeclared(report, consumes),
        )

    @staticmethod
    def _undeclared(
        report: MatchReport, consumes: Mapping[str, Sequence[str]]
    ) -> tuple[tuple[str, str], ...]:
        """Chamadas que atravessaram repos sem o catalogo declarar `consumes`.

        Sem `consumes`, o casamento considera qualquer outro repo como destino
        possivel (`CallRouteMatcher`), e a chamada casa de qualquer forma —
        em silencio. O preco aparece depois: uma rota que exista em dois repos
        fica ambigua sem motivo aparente, e uma ingestao parcial nao sabe que
        precisa trazer o servidor junto. Por isso isto e diagnostico, e nao
        erro: a extracao esta certa, o catalogo e que esta incompleto.
        """
        return tuple(
            sorted(
                {
                    (match.call.repo, match.route.repo)
                    for match in report.matches
                    if match.route.repo != match.call.repo
                    and match.route.repo not in (consumes.get(match.call.repo) or ())
                }
            )
        )
