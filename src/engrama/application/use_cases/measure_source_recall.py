from engrama.application.dto.evaluation import GoldenQuestion, SourceLookup, SourceRecallReport
from engrama.application.dto.knowledge import ChunkHit
from engrama.application.ports.knowledge import GoldenQuestionSource, KnowledgeIndex


class MeasureSourceRecall:
    """Mede se a busca acha a fonte que cada pergunta de ouro espera.

    Nao e o portao 2, que exige resposta certa com fonte certa e precisa de
    LLM. E a parte que da para medir sem nenhum modelo: se o pedaco certo nao
    aparece na busca, nenhuma resposta depois vai citar a fonte certa.

    Fonte que aponta para codigo nao e documento e nao entra na conta
    (`skipped`): quem responde por ela e a camada de estrutura.
    """

    def __init__(self, questions: GoldenQuestionSource, index: KnowledgeIndex) -> None:
        self._questions = questions
        self._index = index

    def execute(self, limit: int = 10) -> SourceRecallReport:
        questions = self._questions.load()
        indexed = {f"{document.repo}/{document.path}" for document in self._index.documents()}

        lookups: list[SourceLookup] = []
        skipped: list[str] = []
        for question in questions:
            hits: list[ChunkHit] | None = None
            for source in question.sources:
                file, _, line = source.partition(":")
                if file not in indexed:
                    skipped.append(source)
                    continue
                if hits is None:
                    hits = self._index.search(question.question, limit)
                lookups.append(self._lookup(question, source, file, line, hits))

        return SourceRecallReport(
            limit=limit,
            questions=len(questions),
            lookups=tuple(lookups),
            skipped=tuple(skipped),
        )

    @staticmethod
    def _lookup(
        question: GoldenQuestion, source: str, file: str, line: str, hits: list[ChunkHit]
    ) -> SourceLookup:
        ranked = [(rank, hit) for rank, hit in enumerate(hits, start=1) if hit.file == file]
        expected = int(line) if line.isdigit() else None
        return SourceLookup(
            question_id=question.id,
            source=source,
            rank=ranked[0][0] if ranked else None,
            line=expected,
            covered=bool(expected and any(hit.covers(expected) for _, hit in ranked)),
        )
