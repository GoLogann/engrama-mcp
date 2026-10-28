import pytest

from engrama.infrastructure.security.secret_scanner import REDACTED, RegexSecretScanner

scanner = RegexSecretScanner()

# Mesmas formas das credenciais listadas em docs/seguranca.md, com valores falsos.
LEAKS = [
    ("      POSTGRES_PASSWORD: devpass123", "devpass123"),
    ("      DB_PASSWORD: devpass123", "devpass123"),
    ("      PGPASSWORD: devpass123", "devpass123"),
    ("  DB_PASSWORD=devpass123", "devpass123"),
    ("  JWT_SECRET=dev-only-trocar", "dev-only-trocar"),
    ("      JWT_SECRET: segredo-falso-de-ci", "segredo-falso-de-ci"),
    ('  connectionstring: "host=localhost user=labsc password=devpass123 dbname=x"', "devpass123"),
    ("            -password=devpass123 \\", "devpass123"),
    ('\t\tsecret = "insecure-default-secret"', "insecure-default-secret"),
    ("DATABASE_URL=postgres://labsc:devpass123@localhost:5432/db", "devpass123"),
    ('token = "ghp_1234567890abcdefghijABCDEFGHIJ123456"', "ghp_1234567890abcdefghijABCDEFGHIJ"),
    ("      API_KEY: ${API_KEY:-dev-key-local}", "dev-key-local"),
    ("      CURATION_API_KEY: ${API_KEY:-dev-key-local}", "dev-key-local"),
    ("      DB_PASSWORD: ${DB_PASSWORD:=devpass123}", "devpass123"),
    ("      RESEARCH_EXPORT_SALT: sal-de-desenvolvimento", "sal-de-desenvolvimento"),
    ("  key_passphrase = frase-de-desenvolvimento", "frase-de-desenvolvimento"),
]


@pytest.mark.parametrize(("line", "secret"), LEAKS)
def test_mascara_credenciais_dos_repos(line, secret):
    redaction = scanner.redact(line)

    assert secret not in redaction.text
    assert REDACTED in redaction.text
    assert redaction.findings


@pytest.mark.parametrize(
    "line",
    [
        "      EXPERT_JWT_SECRET: ${EXPERT_JWT_SECRET:-}",
        "        password=settings.DB_PASSWORD,",
        "    def __init__(self, host: str, port: int, user: str, password: str):",
        "          password: passwordController.text,",
        "- [ ] `JWT_SECRET` e `JWT_EXPIRES_IN` via env",
        "POSTGRES_DB: phishing_quest",
        "      API_KEY: ${API_KEY:-}",
        "      API_KEY: ${API_KEY}",
        # Parametro repassado num exemplo de codigo da documentacao: o valor e
        # a propria chave, entao mascarar estraga o exemplo e nao esconde nada.
        "        self.client = OpenAI(api_key=api_key)",
        "    client = Client(API_KEY=API_KEY)",
    ],
)
def test_preserva_referencias_e_nomes(line):
    assert scanner.redact(line).text == line


def test_valor_diferente_da_chave_continua_mascarado():
    """O caso parecido que nao e repasse: valor de verdade ao lado da chave."""
    redaction = scanner.redact("        self.client = OpenAI(api_key=sk-nao-e-repasse)")

    assert REDACTED in redaction.text
    assert "sk-nao-e-repasse" not in redaction.text


def test_mantem_a_chave_e_informa_a_linha():
    redaction = scanner.redact("a: 1\nDB_PASSWORD=devpass123\n")

    assert redaction.text == f"a: 1\nDB_PASSWORD={REDACTED}\n"
    assert [finding.line for finding in redaction.findings] == [2]


@pytest.mark.parametrize(
    ("path", "excluded"),
    [
        (".env", True),
        ("config/.env.production", True),
        (".env.example", False),
        ("certs/server.pem", True),
        ("phishing-quest.exe", True),
        ("data/articles/paper.pdf", True),
        ("qdrant/phishing_articles.snapshot", True),
        ("evaluation_report_20260115_211101.json", True),
        ("frontend/node_modules/x/index.ts", True),
        ("app/main.py", False),
        ("docs/analise.md", False),
    ],
)
def test_politica_de_arquivos(path, excluded):
    assert scanner.excludes(path) is excluded


def test_mascara_so_o_default_e_preserva_a_variavel():
    redaction = scanner.redact("      API_KEY: ${API_KEY:-dev-key-local}")

    assert redaction.text == f"      API_KEY: ${{API_KEY:-{REDACTED}}}"
