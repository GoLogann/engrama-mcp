"""A leitura de documentos sobre os clones reais dos repos do LABit.

Guarda o que a camada de documentacao promete sobre os quatro repos: quais
arquivos contam como documentacao, o que e decisao, e que a credencial do
`flyway.config` nao chega ao texto indexado. Sem os clones em `.cache/repos`
(criados por `engrama ingest`), os testes sao pulados.
"""

from pathlib import Path

import pytest

from engrama.application.use_cases.read_repository_documents import ReadRepositoryDocuments
from engrama.domain.services import RouteNormalizer
from engrama.domain.value_objects.document_facts import DocumentKind
from engrama.infrastructure.config.yaml_catalog import YamlRepositoryCatalog
from engrama.infrastructure.documents import RepositoryDocumentExtractor
from engrama.infrastructure.git.git_source_repository import GitSourceRepository
from engrama.infrastructure.security.secret_scanner import REDACTED, RegexSecretScanner

ROOT = Path(__file__).parents[2]
REPOS = ROOT / ".cache" / "repos"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def documents_by_repo():
    catalog = YamlRepositoryCatalog(ROOT / "config" / "repos.yaml").load()
    missing = [spec.repo.name for spec in catalog.repos if not (REPOS / spec.repo.name).is_dir()]
    if missing:
        pytest.skip(f"clones ausentes ({', '.join(missing)}); rode `engrama ingest`")
    read = ReadRepositoryDocuments(
        GitSourceRepository(ROOT / ".cache", RegexSecretScanner()),
        RepositoryDocumentExtractor(RouteNormalizer()),
        RegexSecretScanner(),
    )
    return {spec.repo.name: read.execute(spec) for spec in catalog.repos}


def paths_of(documents):
    return {document.path for document in documents.facts.documents}


def test_le_os_documentos_dos_repos(documents_by_repo):
    assert paths_of(documents_by_repo["phishforge-frontend"]) == {
        "README.md",
        "nginx.conf.template",
        "package.json",
    }
    assert paths_of(documents_by_repo["phishing_quest"]) == {"README.md"}
    quest_api = paths_of(documents_by_repo["phishing-quest-api"])
    assert "PLANO_EXECUCAO.md" in quest_api
    assert "migrate/flyway-prod.config" in quest_api


def test_nao_indexa_dados_nem_pasta_de_plataforma(documents_by_repo):
    """`data/articles/phishing_examples.md` sao exemplos de phishing (1490
    linhas), e o README do `ios/` e template do Xcode: nenhum dos dois
    responde pergunta sobre o projeto."""
    assert "data/articles/phishing_examples.md" not in paths_of(documents_by_repo["phishforge-api"])
    assert not any(
        path.startswith("ios/") for path in paths_of(documents_by_repo["phishing_quest"])
    )


def test_os_dois_adrs_da_quest_api_sao_decisao_com_status(documents_by_repo):
    decisions = [
        document
        for document in documents_by_repo["phishing-quest-api"].facts.documents
        if document.kind is DocumentKind.DECISION
    ]

    assert sorted(document.path for document in decisions) == [
        "docs/decisoes/0001-path-registro-usuario.md",
        "docs/decisoes/0002-estrategia-testes-e-ci.md",
    ]
    assert all(document.status for document in decisions)
    assert all(document.title.startswith("ADR 000") for document in decisions)


@pytest.mark.parametrize("repo", ["phishforge-api", "phishing-quest-api"])
def test_a_senha_do_flyway_nao_chega_ao_texto_indexado(documents_by_repo, repo):
    """A conferencia e na linha da senha, nao no arquivo inteiro: na
    phishforge-api a senha de desenvolvimento e a propria palavra
    `phishforge`, que tambem e o nome do banco, do usuario e do host. Valor
    assim nao da para apagar do texto todo sem destruir o documento."""
    documents = documents_by_repo[repo]
    config = next(
        document
        for document in documents.facts.documents
        if document.path == "migrate/flyway.config"
    )
    original = (REPOS / repo / "migrate" / "flyway.config").read_text(errors="replace")
    secret = next(
        line.split("=", 1)[1].strip()
        for line in original.splitlines()
        if line.startswith("flyway.password=")
    )
    password_line = next(
        line for line in config.text.splitlines() if line.startswith("flyway.password=")
    )

    assert secret not in password_line
    assert password_line == f"flyway.password={REDACTED}"
    # O resto do arquivo, que e o que responde a pergunta t12, continua inteiro.
    assert "flyway.locations=" in config.text


def test_as_rotas_citadas_nos_documentos_sao_encontradas(documents_by_repo):
    mentions = documents_by_repo["phishforge-api"].facts.mentions

    assert len(mentions) > 20, "docs/integracao_api.md descreve as rotas da API"
    assert all(mention.evidence.line for mention in mentions)
    assert any(str(mention.route).startswith("POST /api/v1/generate") for mention in mentions)
