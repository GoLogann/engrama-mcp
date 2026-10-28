from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GoldenQuestion:
    """Uma pergunta de ouro de `eval/golden_questions.yaml`."""

    id: str
    audience: str
    layer: str
    question: str
    sources: tuple[str, ...]
    must_contain: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceLookup:
    """Se a busca trouxe a fonte esperada de uma pergunta, e em que posicao.

    `rank` e a posicao (1-based) do primeiro pedaco do arquivo esperado;
    `line` e a linha que a fonte cita, e `covered` diz se o pedaco encontrado
    contem essa linha. Sem `rank`, a busca nao trouxe o arquivo.
    """

    question_id: str
    source: str
    rank: int | None = None
    line: int | None = None
    covered: bool = False

    @property
    def found(self) -> bool:
        return self.rank is not None


@dataclass(frozen=True, slots=True)
class SourceRecallReport:
    """Quanto da fonte esperada a busca encontra, sem LLM nenhum no meio.

    Mede so as fontes que sao documento indexado: as que apontam para codigo
    pertencem a camada de estrutura e entram em `skipped`.
    """

    limit: int
    questions: int
    lookups: tuple[SourceLookup, ...]
    skipped: tuple[str, ...] = ()

    @property
    def found(self) -> int:
        return sum(1 for lookup in self.lookups if lookup.found)

    @property
    def covered(self) -> int:
        return sum(1 for lookup in self.lookups if lookup.covered)

    @property
    def file_recall(self) -> float:
        return self.found / len(self.lookups) if self.lookups else 0.0

    @property
    def line_recall(self) -> float:
        lines = [lookup for lookup in self.lookups if lookup.line is not None]
        return sum(1 for lookup in lines if lookup.covered) / len(lines) if lines else 0.0

    @property
    def misses(self) -> tuple[SourceLookup, ...]:
        return tuple(lookup for lookup in self.lookups if not lookup.found)
