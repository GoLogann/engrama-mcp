import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass

_NUMBER_LIST = r"#(?P<first>\d+)(?P<rest>(?:\s*(?:,|/|\be\b|\band\b)\s*#\d+)*)"

# O qualificador vem logo depois do numero, mas pode haver um participio no
# meio: "issue #38 aberta no front". Uma palavra so, para "issue #7 e o front
# tambem usa" nao virar citacao do front.
_QUALIFIER = r"^[\s,;(]*(?:\w+\s+)?(?:d[oa]|n[oa])\s+"
# "issue #5 do backend": o repo do servidor nao esta no texto, esta em `consumes`.
_BACKEND = re.compile(rf"(?i){_QUALIFIER}(?:back-?end|servidor)\b")
# Qualificador que aponta para outro repo sem nomea-lo de forma resolvivel:
# "do app", "no front". Quem consome este repo nao esta em `consumes` (que
# lista quem ele consome), entao nao da para resolver.
_FOREIGN = re.compile(rf"(?i){_QUALIFIER}(?:app|aplicativo|front(?:-?end)?|mobile|cliente|site)\b")


@dataclass(frozen=True, slots=True)
class IssueCitation:
    """Uma issue citada num texto, e de qual repo ela e."""

    repo: str
    number: int


@dataclass(frozen=True, slots=True)
class CitationReport:
    """O que a leitura de uma linha achou.

    `unresolved` sao numeros de issue cuja citacao aponta para outro repo sem
    dizer qual de forma resolvivel. Ficam de fora de proposito: atribuir ao
    proprio repo gravaria a issue errada com confianca alta, que e pior do que
    nao gravar.
    """

    found: tuple[IssueCitation, ...] = ()
    unresolved: tuple[int, ...] = ()


class IssueCitationReader:
    """Le citacoes a issues num texto, sem saber de onde o texto veio.

    Reconhece `issue #7`, `issues #12 e #13` (do proprio repo) e
    `phishforge-api #5 e #6` (de outro repo do catalogo). Um `#7` solto nao
    conta: e ambiguo demais.

    `issue #N` vale para o repo do texto, a menos que logo depois venha um
    qualificador: `do repo <nome>` / `do <nome>` aponta para esse repo do
    catalogo, `do backend` aponta para o unico repo em `consumes`, e um
    qualificador generico de cliente (`do app`, `no front`) nao da para
    resolver, porque `consumes` lista quem o repo consome e nao quem o
    consome.

    Quem chama decide o que e "logo depois": em codigo, so uma linha de
    comentario continua a frase; em Markdown, a linha seguinte continua o
    paragrafo, a menos que esteja em branco. Por isso `following` e parametro,
    e nao algo que este servico deduz.
    """

    def __init__(self, known_repos: Collection[str]) -> None:
        names = "|".join(re.escape(name) for name in sorted(known_repos, key=len, reverse=True))
        self._canonical = {name.lower(): name for name in known_repos}
        self._same_repo = re.compile(rf"(?i)\bissues?\s*{_NUMBER_LIST}")
        self._other_repo = re.compile(rf"(?<![\w/-])(?P<repo>{names})\s*{_NUMBER_LIST}")
        # A crase e as aspas aparecem em "no repositorio `phishing_quest`".
        self._named_after = re.compile(
            rf"(?i){_QUALIFIER}(?:repo(?:sit[óo]rio)?\s+)?[`'\"]?(?P<repo>{names})\b"
        )

    def read(
        self,
        line: str,
        following: str,
        *,
        own_repo: str,
        consumes: Sequence[str] = (),
    ) -> CitationReport:
        found: list[IssueCitation] = []
        unresolved: list[int] = []
        for match in self._same_repo.finditer(line):
            tail = f"{line[match.end() :]} {following}"
            target = self._target(tail, own_repo=own_repo, consumes=consumes)
            if target is None:
                unresolved += _numbers(match)
            else:
                found += [IssueCitation(target, number) for number in _numbers(match)]
        for match in self._other_repo.finditer(line):
            repo = self._canonical.get(match.group("repo").lower(), match.group("repo"))
            found += [IssueCitation(repo, number) for number in _numbers(match)]
        return CitationReport(tuple(found), tuple(unresolved))

    def _target(self, tail: str, *, own_repo: str, consumes: Sequence[str]) -> str | None:
        """O repo dono da issue, ou `None` quando aponta para fora e nao da
        para dizer para onde. `None` nunca significa "assume o proprio"."""
        if named := self._named_after.match(tail):
            return self._canonical[named.group("repo").lower()]
        if _BACKEND.match(tail):
            return consumes[0] if len(consumes) == 1 else None
        if _FOREIGN.match(tail):
            return None
        return own_repo


def _numbers(match: re.Match[str]) -> list[int]:
    return [int(n) for n in (match.group("first"), *re.findall(r"#(\d+)", match.group("rest")))]
