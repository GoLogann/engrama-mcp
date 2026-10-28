from dataclasses import dataclass

from engrama.domain.entities import Endpoint
from engrama.domain.value_objects.document_facts import RouteMention


@dataclass(frozen=True, slots=True)
class MentionMatch:
    mention: RouteMention
    endpoint: Endpoint


@dataclass(frozen=True, slots=True)
class MentionReport:
    matches: tuple[MentionMatch, ...]
    unmatched: tuple[RouteMention, ...]
    ambiguous: tuple[tuple[RouteMention, tuple[Endpoint, ...]], ...]


def _method_and_path(shape: str) -> tuple[str, str]:
    method, _, path = shape.partition(" ")
    return method, path


class RouteMentionMatcher:
    """Liga uma rota citada num documento ao endpoint que ela descreve.

    A citacao vale so para endpoints do mesmo repo: um documento que escreve
    `GET /api/v1/cues`, rota que existe nas duas APIs, nao afirma nada sobre a
    outra. A comparacao e por forma (nomes de parametro nao contam).

    Documento costuma escrever a rota sem o prefixo com que o servidor a
    registra: o ADR 0001 da Quest API fala de `POST /users/register`, e o
    grafo tem `POST /api/v1/users/register`. Por isso, quando nada casa
    exatamente, vale o endpoint cujo caminho termina na citacao — e so se for
    um unico. O prefixo omitido comeca em `/`, entao o encaixe cai sempre em
    limite de segmento: `/users` nao casa com `/myusers`.
    """

    def match(self, mentions: list[RouteMention], endpoints: list[Endpoint]) -> MentionReport:
        matches: list[MentionMatch] = []
        unmatched: list[RouteMention] = []
        ambiguous: list[tuple[RouteMention, tuple[Endpoint, ...]]] = []
        for mention in mentions:
            candidates = self._candidates(mention, endpoints)
            if len(candidates) == 1:
                matches.append(MentionMatch(mention, candidates[0]))
            elif candidates:
                ambiguous.append((mention, candidates))
            else:
                unmatched.append(mention)
        return MentionReport(tuple(matches), tuple(unmatched), tuple(ambiguous))

    def _candidates(self, mention: RouteMention, endpoints: list[Endpoint]) -> tuple[Endpoint, ...]:
        same_repo = [e for e in endpoints if e.repo == mention.repo]
        shape = mention.route.shape
        if exact := tuple(e for e in same_repo if e.route.shape == shape):
            return exact
        method, path = _method_and_path(shape)
        return tuple(
            endpoint
            for endpoint in same_repo
            for endpoint_method, endpoint_path in [_method_and_path(endpoint.route.shape)]
            if endpoint_method == method and endpoint_path != path and endpoint_path.endswith(path)
        )
