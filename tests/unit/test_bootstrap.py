from typer.testing import CliRunner

from engrama.bootstrap.container import Container
from engrama.entrypoints.cli.app import build_cli


def test_container_resolve_settings_com_padroes(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENGRAMA_LLM_MODEL", raising=False)

    settings = Container().settings()

    assert settings.llm_model == "claude-opus-5-5"
    assert settings.neo4j_uri == "bolt://localhost:7687"


def test_cli_version():
    result = CliRunner().invoke(build_cli(), ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0"
