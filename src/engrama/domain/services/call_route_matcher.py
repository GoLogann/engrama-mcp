from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from engrama.domain.value_objects.code_facts import CallSite, DeclaredRoute


@dataclass(frozen=True, slots=True)
class RouteMatch:
    call: CallSite
    route: DeclaredRoute


@dataclass(frozen=True, slots=True)
class MatchReport:
    matches: tuple[RouteMatch, ...]
    unmatched_calls: tuple[CallSite, ...]
    ambiguous_calls: tuple[tuple[CallSite, tuple[DeclaredRoute, ...]], ...]
    routes_without_callers: tuple[DeclaredRoute, ...]


class CallRouteMatcher:
    """Casa cada chamada com a rota que ela atinge.

    A comparacao e por metodo e forma do caminho, ignorando nomes de
    parametro. `consumes` diz quais repos cada cliente chama; sem essa
    informacao, um cliente pode atingir qualquer outro repo, e uma rota que
    exista em dois deles (como `GET /api/v1/cues`) fica ambigua.
    """

    def __init__(self, consumes: Mapping[str, Collection[str]]) -> None:
        self._consumes = consumes

    def match(self, calls: Sequence[CallSite], routes: Sequence[DeclaredRoute]) -> MatchReport:
        by_shape: dict[tuple[str, str], list[DeclaredRoute]] = defaultdict(list)
        for route in routes:
            by_shape[(route.repo, route.route.shape)].append(route)
        repos = {route.repo for route in routes}

        matches: list[RouteMatch] = []
        unmatched: list[CallSite] = []
        ambiguous: list[tuple[CallSite, tuple[DeclaredRoute, ...]]] = []
        for call in calls:
            targets = self._consumes.get(call.repo) or sorted(repos - {call.repo})
            candidates = tuple(
                route
                for target in targets
                for route in by_shape.get((target, call.route.shape), ())
            )
            if len(candidates) == 1:
                matches.append(RouteMatch(call, candidates[0]))
            elif candidates:
                ambiguous.append((call, candidates))
            else:
                unmatched.append(call)

        called = {match.route for match in matches}
        return MatchReport(
            matches=tuple(matches),
            unmatched_calls=tuple(unmatched),
            ambiguous_calls=tuple(ambiguous),
            routes_without_callers=tuple(route for route in routes if route not in called),
        )
