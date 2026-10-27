"""O filtro de segredos sobre as linhas reais dos repos do LABit.

Cada entrada aponta uma linha de `docs/seguranca.md` e traz so um padrao para
achar o valor (grupo `v`); o valor em si nunca e escrito aqui: o teste o le do
proprio clone, roda `redact` no arquivo inteiro e confere que ele sumiu da linha.
Sem o clone em `.cache/repos` (criado por `engrama ingest`), o teste e pulado.
"""

import re
from pathlib import Path

import pytest

from engrama.infrastructure.security.secret_scanner import REDACTED, RegexSecretScanner

REPOS = Path(__file__).parents[2] / ".cache" / "repos"

# (arquivo, linha, padrao do valor)
SECRET_LINES = [
    ("phishing-quest-api/docker-compose.yml", 9, r"POSTGRES_PASSWORD:\s*(?P<v>\S+)"),
    ("phishing-quest-api/config.yaml", 15, r"password=(?P<v>\S+)"),
    ("phishing-quest-api/PLANO_EXECUCAO.md", 23, r"DB_PASSWORD=(?P<v>\S+)"),
    ("phishing-quest-api/PLANO_EXECUCAO.md", 27, r"JWT_SECRET=(?P<v>\S+)"),
    ("phishing-quest-api/core/service/jwt_service.go", 39, r'secret = "(?P<v>[^"]+)"'),
    ("phishing-quest-api/migrate/flyway.config", 3, r"flyway\.password=(?P<v>\S+)"),
    ("phishing-quest-api/.github/workflows/workflow_pr_ci.yml", 90, r"PASSWORD:\s*(?P<v>\S+)"),
    ("phishing-quest-api/.github/workflows/workflow_pr_ci.yml", 103, r"PASSWORD:\s*(?P<v>\S+)"),
    ("phishing-quest-api/.github/workflows/workflow_pr_ci.yml", 106, r"SECRET:\s*(?P<v>\S+)"),
    ("phishing-quest-api/.github/workflows/workflow_pr_ci.yml", 107, r"SALT:\s*(?P<v>\S+)"),
    ("phishing-quest-api/.github/workflows/workflow_pr_ci.yml", 129, r"-password=(?P<v>\S+)"),
    ("phishforge-api/docker-compose.yml", 9, r"POSTGRES_PASSWORD:\s*(?P<v>\S+)"),
    ("phishforge-api/docker-compose.yml", 120, r"DB_PASSWORD:\s*(?P<v>\S+)"),
    ("phishforge-api/docker-compose.yml", 135, r"API_KEY:\s*\$\{API_KEY:-(?P<v>[^}]+)\}"),
    ("phishforge-api/docker-compose.yml", 174, r"API_KEY:\s*\$\{API_KEY:-(?P<v>[^}]+)\}"),
    ("phishforge-api/docker-compose.yml", 195, r"PGPASSWORD:\s*(?P<v>\S+)"),
    ("phishforge-api/migrate/flyway.config", 3, r"flyway\.password=(?P<v>\S+)"),
]

scanner = RegexSecretScanner()


@pytest.mark.integration
@pytest.mark.parametrize(
    ("path", "line", "pattern"), SECRET_LINES, ids=[f"{p}:{n}" for p, n, _ in SECRET_LINES]
)
def test_credencial_de_desenvolvimento_dos_repos_e_mascarada(path, line, pattern):
    file = REPOS / path
    if not file.is_file():
        pytest.skip(f"clone ausente ({path}); rode `engrama ingest`")
    original = file.read_text(errors="replace")
    match = re.search(pattern, original.splitlines()[line - 1])
    assert match, f"{path}:{line} nao tem mais o formato esperado; revise docs/seguranca.md"
    secret = match.group("v").strip("\"'")

    redacted_line = scanner.redact(original).text.splitlines()[line - 1]

    assert secret not in redacted_line
    assert REDACTED in redacted_line
