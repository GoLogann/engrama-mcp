"""A CLI dos comandos da camada de documentacao.

Os relatorios sao o que o dev le para decidir, e e neles que mora o risco de
dizer mais do que foi medido. Aqui os casos de uso sao fakes: o que se testa e
o codigo de saida e o texto.
"""

from datetime import UTC, datetime

from typer.testing import CliRunner

from engrama.application.dto.documentation import DocumentSummary, IndexingReport
from engrama.application.dto.evaluation import SkippedSource, SourceLookup, SourceRecallReport
from engrama.application.dto.knowledge import ChunkHit
from engrama.domain.value_objects import Evidence, HttpMethod, HttpRoute
from engrama.domain.value_objects.document_facts import RouteMention
from engrama.entrypoints.cli.app import build_cli

C = "c" * 40
T0 = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)
runner = CliRunner()


class Fake:
    def __init__(self, result):
        self._result = result

    def execute(self, *args, **kwargs):
        return self._result


def cli(**overrides):
    def unused():
        raise AssertionError("caso de uso nao deveria ser criado")

    factories = {
        "build_structural_graph": unused,
        "check_structure": unused,
        "index_documents": unused,
        "search_knowledge": unused,
        "measure_source_recall": unused,
    }
    return build_cli(**(factories | {k: (lambda v=v: Fake(v)) for k, v in overrides.items()}))


def summary(**overrides):
    args = {
        "repo": "forge-api",
        "documents": 3,
        "decisions": 1,
        "chunks": 12,
        "endpoints_documented": 2,
        "redactions": 1,
    }
    return DocumentSummary(**(args | overrides))


def mention(route="POST /api/v1/items"):
    method, path = route.split(" ")
    return RouteMention(
        "forge-api",
        "docs/api.md",
        HttpRoute(HttpMethod(method), path),
        Evidence.in_code("forge-api", "docs/api.md", C, 7),
    )


def hit(**overrides):
    args = {
        "repo": "forge-api",
        "path": "README.md",
        "first_line": 52,
        "last_line": 60,
        "heading": "Instalação",
        "text": "Rode o compose.\nsegunda linha",
        "score": 3.5,
        "document_title": "Forge",
        "document_kind": "Doc",
        "ingested_at": T0,
    }
    return ChunkHit(**(args | overrides))


def test_index_docs_mostra_o_resumo_por_repo():
    report = IndexingReport(repos=(summary(),), known_endpoints=75)

    result = runner.invoke(cli(index_documents=report), ["index-docs"])

    assert result.exit_code == 0
    assert "forge-api: 3 documentos, 1 decisões, 12 pedaços" in result.stdout
    assert "1 valores mascarados" in result.stdout
    assert "Endpoints conhecidos no grafo: 75" in result.stdout


def test_index_docs_avisa_quando_nao_ha_estrutura_no_grafo():
    report = IndexingReport(repos=(summary(endpoints_documented=0),), known_endpoints=0)

    result = runner.invoke(cli(index_documents=report), ["index-docs"])

    assert "engrama ingest" in result.stdout


def test_index_docs_lista_a_rota_citada_que_nenhum_endpoint_expoe():
    report = IndexingReport(
        repos=(summary(),), known_endpoints=75, unmatched=(mention(),), ambiguous=(mention(),)
    )

    result = runner.invoke(cli(index_documents=report), ["index-docs"])

    assert "sem endpoint: POST /api/v1/items em forge-api/docs/api.md:7" in result.stdout
    assert "ambígua: POST /api/v1/items" in result.stdout


def test_search_mostra_a_fonte_com_linha():
    result = runner.invoke(cli(search_knowledge=[hit()]), ["search", "compose"])

    assert result.exit_code == 0
    assert "1. forge-api/README.md:52 (3.5000) Forge — Instalação" in result.stdout
    assert "Rode o compose." in result.stdout


def test_search_sem_resultado_falha_e_sugere_indexar():
    result = runner.invoke(cli(search_knowledge=[]), ["search", "nada"])

    assert result.exit_code == 1
    assert "index-docs" in result.stdout


def recall_report(**overrides):
    args = {
        "limit": 10,
        "questions": 40,
        "lookups": (
            SourceLookup("n01", "api/README.md:3", rank=1, line=3, covered=True),
            SourceLookup("n17", "api/README.md:52", rank=None, line=52),
        ),
        "skipped": (SkippedSource("t08", "front/nginx.conf.template:14"),),
        "unmeasured": ("t08",),
    }
    return SourceRecallReport(**(args | overrides))


def test_check_sources_nao_chama_de_codigo_o_que_nao_conferiu():
    result = runner.invoke(cli(measure_source_recall=recall_report()), ["check-sources"])

    assert result.exit_code == 0
    assert "Fontes medidas: 2 de 3" in result.stdout
    assert "código" not in result.stdout
    assert "Fora do índice de documentos (1): .template 1" in result.stdout


def test_check_sources_nomeia_a_pergunta_que_ficou_sem_medida():
    result = runner.invoke(cli(measure_source_recall=recall_report()), ["check-sources"])

    assert "sem nenhuma fonte medida (1)" in result.stdout
    assert "t08: front/nginx.conf.template:14" in result.stdout


def test_check_sources_mostra_acerto_e_o_que_faltou():
    result = runner.invoke(cli(measure_source_recall=recall_report()), ["check-sources"])

    assert "Arquivo certo na lista: 1/2 (50%)" in result.stdout
    assert "n17: api/README.md:52" in result.stdout
    assert "n01: api/README.md:3 em 1º linha coberta" in result.stdout


def test_index_docs_diz_quantos_pedacos_ficaram_com_vetor():
    report = IndexingReport(repos=(summary(),), known_endpoints=75, vectors=12)

    result = runner.invoke(cli(index_documents=report), ["index-docs"])

    assert "Pedaços com vetor: 12 de 12" in result.stdout
    assert "não enxerga" not in result.stdout


def test_index_docs_avisa_quando_falta_vetor_em_algum_pedaco():
    report = IndexingReport(repos=(summary(),), known_endpoints=75, vectors=5)

    result = runner.invoke(cli(index_documents=report), ["index-docs"])

    assert "Pedaços com vetor: 5 de 12" in result.stdout
    assert "A metade vetorial da busca não enxerga os pedaços sem vetor." in result.stdout


def test_check_sources_diz_por_qual_motor_a_busca_ordenou():
    result = runner.invoke(
        cli(measure_source_recall=recall_report(ranking="vetor")), ["check-sources"]
    )

    assert "ordenadas por vetor" in result.stdout
    assert "Reserva por palavra" not in result.stdout


def test_check_sources_avisa_quando_mediu_a_reserva_por_palavra():
    result = runner.invoke(
        cli(measure_source_recall=recall_report(ranking="palavra")), ["check-sources"]
    )

    assert "ordenadas por palavra" in result.stdout
    assert "VOYAGE_API_KEY" in result.stdout
