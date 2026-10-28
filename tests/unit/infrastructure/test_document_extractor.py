from engrama.application.dto.ingestion import RepositorySpec
from engrama.domain.entities import Repo, Stack
from engrama.domain.services import RouteNormalizer
from engrama.domain.value_objects.document_facts import DocumentKind
from engrama.infrastructure.documents import RepositoryDocumentExtractor
from engrama.infrastructure.security.secret_scanner import RegexSecretScanner
from tests.fakes.sources import InMemorySourceTree

C = "a" * 40
API = Repo("forge-api", "forge", "https://github.com/x/forge-api", C, Stack.PYTHON_FASTAPI)
SPEC = RepositorySpec(API)


def extract(files, spec=SPEC):
    tree = InMemorySourceTree(spec.repo, files, scanner=RegexSecretScanner())
    return RepositoryDocumentExtractor(RouteNormalizer()).extract(tree, spec)


def paths(facts):
    return [document.path for document in facts.documents]


def test_le_readme_docs_adrs_e_configuracao():
    facts = extract(
        {
            "README.md": "# Forge\n\ntexto",
            "docs/architecture.md": "# Arquitetura\n\ntexto",
            "docs/decisoes/0001-rota.md": "# ADR 0001\n\n- **Status:** aceita\n",
            "migrate/flyway.config": "flyway.url=jdbc:postgresql://host:5432/db",
            "nginx.conf.template": "location /api/v1/ { proxy_pass ${API_UPSTREAM}; }",
            "package.json": '{"name": "forge"}',
            "app/main.py": "print('nao e documento')",
        }
    )

    assert paths(facts) == [
        "README.md",
        "docs/architecture.md",
        "docs/decisoes/0001-rota.md",
        "migrate/flyway.config",
        "nginx.conf.template",
        "package.json",
    ]


def test_decisao_vem_do_diretorio_com_titulo_e_status():
    facts = extract({"docs/decisoes/0001-rota.md": "# ADR 0001 — Rota\n\n- **Status:** aceita\n"})

    decision = facts.documents[0]
    assert decision.kind is DocumentKind.DECISION
    assert decision.title == "ADR 0001 — Rota"
    assert decision.status == "aceita"


def test_documento_comum_nao_tem_status_mesmo_com_a_palavra_no_texto():
    facts = extract({"docs/plano.md": "# Plano\n\nStatus: em andamento\n"})

    assert facts.documents[0].kind is DocumentKind.DOC
    assert facts.documents[0].status is None


def test_titulo_sem_cabecalho_e_o_nome_do_arquivo():
    facts = extract({"migrate/flyway.config": "flyway.user=app"})

    assert facts.documents[0].title == "flyway.config"


def test_titulo_ignora_cerquilha_dentro_de_bloco_de_codigo():
    facts = extract({"README.md": "```bash\n# cp .env.example .env\n```\n\n# Forge de verdade\n"})

    assert facts.documents[0].title == "Forge de verdade"


def test_ignora_diretorio_de_dados_plataforma_e_teste():
    facts = extract(
        {
            "README.md": "# Forge",
            "data/articles/phishing_examples.md": "# Exemplos de phishing",
            "ios/Runner/README.md": "# template do Xcode",
            "tests/fixtures/caso.md": "# caso",
        }
    )

    assert paths(facts) == ["README.md"]


def test_package_json_de_subprojeto_nao_e_documento():
    facts = extract({"frontend/package.json": '{"name": "x"}', "README.md": "# Forge"})

    assert paths(facts) == ["README.md"]


def test_arquivo_excluido_pela_politica_de_segredos_nao_e_lido():
    facts = extract({".env.example": "API_KEY=", "README.md": "# Forge"})

    assert paths(facts) == ["README.md"]


def test_rota_escrita_no_texto_vira_citacao_com_a_linha():
    text = "# API\n\nUse `POST /api/v1/generate`.\n\nE GET /api/v1/emails/{email_id}\n"

    facts = extract({"docs/api.md": text})

    assert [(m.evidence.line, str(m.route)) for m in facts.mentions] == [
        (3, "POST /api/v1/generate"),
        (5, "GET /api/v1/emails/{email_id}"),
    ]


def test_pontuacao_da_frase_sai_e_o_parametro_fica():
    facts = extract({"docs/api.md": "Chame POST /api/v1/x/{id}, depois **GET /api/v1/y**."})

    assert [str(m.route) for m in facts.mentions] == ["POST /api/v1/x/{id}", "GET /api/v1/y"]


def test_url_inteira_vira_rota_sem_o_host():
    facts = extract({"docs/api.md": "curl -X POST http://localhost:8000/api/v1/generate/batch"})

    assert [str(m.route) for m in facts.mentions] == ["POST /api/v1/generate/batch"]


def test_rota_repetida_na_mesma_linha_conta_uma_vez():
    facts = extract({"docs/api.md": "GET /api/v1/x e GET /api/v1/x"})

    assert len(facts.mentions) == 1


def test_rota_fora_da_forma_canonica_vira_diagnostico():
    facts = extract({"docs/api.md": "# API\n\nGET /api/v1/items/{id}.json\n"})

    assert facts.mentions == ()
    assert len(facts.diagnostics) == 1
    assert "docs/api.md:3" in facts.diagnostics[0]


def test_metodo_em_minuscula_nao_e_citacao_de_rota():
    facts = extract({"docs/api.md": "get /api/v1/x nao e citacao"})

    assert facts.mentions == ()


def test_configuracao_do_servidor_web_e_documento():
    """`nginx.conf.template` diz como o frontend chega na API em producao, que
    e a pergunta t08. E documentacao de operacao, nao dado (ADR 0010, emenda
    de 28/10/2026). `.conf.template` precisa casar por fim de nome composto:
    o sufixo do arquivo e `.template`, nao `.conf`."""
    facts = extract(
        {
            "nginx.conf": "listen 3000;",
            "nginx.conf.template": "proxy_pass ${API_UPSTREAM};",
            "index.html.template": "<html>",
        }
    )

    assert paths(facts) == ["nginx.conf", "nginx.conf.template"]
