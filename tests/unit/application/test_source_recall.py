from engrama.application.dto.evaluation import GoldenQuestion
from engrama.application.dto.knowledge import ChunkHit, IndexedDocument
from engrama.application.ports.knowledge import GoldenQuestionSource, KnowledgeIndex
from engrama.application.use_cases.measure_source_recall import MeasureSourceRecall


class StaticQuestions(GoldenQuestionSource):
    def __init__(self, *questions: GoldenQuestion):
        self._questions = questions

    def load(self) -> tuple[GoldenQuestion, ...]:
        return self._questions


class StubIndex(KnowledgeIndex):
    """Indice que devolve sempre os mesmos pedacos, na ordem dada."""

    def __init__(self, hits: list[ChunkHit], documents: list[IndexedDocument]):
        self._hits = hits
        self._documents = documents
        self.queries: list[str] = []

    def search(self, query: str, limit: int = 10) -> list[ChunkHit]:
        self.queries.append(query)
        return self._hits[:limit]

    def documents(self) -> list[IndexedDocument]:
        return self._documents


def hit(repo, path, first_line, last_line, score=1.0):
    return ChunkHit(
        repo=repo,
        path=path,
        first_line=first_line,
        last_line=last_line,
        heading="",
        text="texto",
        score=score,
        document_title="t",
        document_kind="Doc",
    )


def question(id_, sources, layer="documentacao"):
    return GoldenQuestion(id_, "nao_tecnico", layer, "Pergunta?", tuple(sources))


def recall(asked, index, **kwargs):
    return MeasureSourceRecall(StaticQuestions(asked), index).execute(**kwargs)


README = IndexedDocument("api", "README.md", "Doc", "API", 3)
OUTRO = IndexedDocument("api", "docs/outro.md", "Doc", "Outro", 1)


def test_acha_a_fonte_e_a_linha_dentro_do_pedaco():
    index = StubIndex([hit("api", "README.md", 50, 60)], [README])

    report = recall(question("n01", ["api/README.md:52"]), index)

    assert report.found == 1
    assert report.file_recall == 1.0
    assert report.line_recall == 1.0
    assert report.lookups[0].rank == 1


def test_arquivo_certo_com_a_linha_fora_do_pedaco():
    index = StubIndex([hit("api", "README.md", 1, 10)], [README])

    report = recall(question("n01", ["api/README.md:52"]), index)

    assert report.found == 1
    assert report.covered == 0
    assert report.line_recall == 0.0


def test_posicao_e_a_do_primeiro_pedaco_do_arquivo():
    index = StubIndex(
        [hit("api", "docs/outro.md", 1, 5), hit("api", "README.md", 50, 60)], [README, OUTRO]
    )

    report = recall(question("n01", ["api/README.md:52"]), index)

    assert report.lookups[0].rank == 2


def test_fonte_que_nao_e_documento_indexado_fica_de_fora():
    index = StubIndex([], [README])
    asked = question("t01", ["api/app/main.py:10", "api/README.md:1"])

    report = recall(asked, index)

    assert report.skipped == ("api/app/main.py:10",)
    assert len(report.lookups) == 1


def test_pergunta_sem_fonte_de_documento_nao_faz_busca():
    index = StubIndex([], [README])
    asked = question("t01", ["api/app/main.py:10"], layer="estrutura")

    report = recall(asked, index)

    assert index.queries == []
    assert report.lookups == ()
    assert report.file_recall == 0.0


def test_fonte_sem_linha_conta_no_arquivo_e_nao_na_linha():
    index = StubIndex([hit("api", "README.md", 1, 10)], [README])

    report = recall(question("n01", ["api/README.md"]), index)

    assert report.file_recall == 1.0
    assert report.line_recall == 0.0, "sem linha citada, nao ha cobertura de linha a medir"


def test_fonte_ausente_entra_em_misses():
    index = StubIndex([hit("api", "docs/outro.md", 1, 5)], [README, OUTRO])

    report = recall(question("n01", ["api/README.md:52"]), index)

    assert [miss.source for miss in report.misses] == ["api/README.md:52"]
    assert report.file_recall == 0.0


def test_limite_e_repassado_para_a_busca():
    index = StubIndex([hit("api", "README.md", 1, 10)] * 3, [README])

    report = recall(question("n01", ["api/README.md:5"]), index, limit=2)

    assert report.limit == 2
