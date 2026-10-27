from typer.testing import CliRunner

from engrama.application.dto.structure_check import RouteFact, StructureCheckReport
from engrama.bootstrap.container import Container
from engrama.entrypoints.cli.app import build_cli


class FakeCheck:
    def __init__(self, report: StructureCheckReport):
        self._report = report

    def execute(self) -> StructureCheckReport:
        return self._report


def cli(report: StructureCheckReport | None = None):
    def unused():
        raise AssertionError("caso de uso nao deveria ser criado")

    return build_cli(
        build_structural_graph=unused,
        check_structure=(lambda: FakeCheck(report)) if report else unused,
    )


def test_container_resolve_settings_com_padroes(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENGRAMA_LLM_MODEL", raising=False)

    settings = Container().settings()

    assert settings.llm_model == "claude-opus-5-5"
    assert settings.neo4j_uri == "bolt://localhost:7687"


def test_cli_version_nao_cria_casos_de_uso():
    result = CliRunner().invoke(cli(), ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0"


def test_check_structure_falha_quando_o_portao_reprova():
    missing = RouteFact("api", "app/r.py", 3, "GET /x")
    report = StructureCheckReport(1, 0, (missing,), (), (), ())

    result = CliRunner().invoke(cli(report), ["check-structure"])

    assert result.exit_code == 1
    assert "Rotas faltando (1)" in result.stdout
    assert "Portão 1: reprovado" in result.stdout


def test_check_structure_aprova():
    result = CliRunner().invoke(
        cli(StructureCheckReport(1, 1, (), (), (), ())), ["check-structure"]
    )

    assert result.exit_code == 0
    assert "Portão 1: aprovado" in result.stdout
