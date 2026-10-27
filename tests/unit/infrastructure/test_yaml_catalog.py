from pathlib import Path

import pytest

from engrama.domain.entities import Stack
from engrama.infrastructure.config.yaml_catalog import YamlRepositoryCatalog

CATALOG = Path(__file__).parents[3] / "config" / "repos.yaml"


@pytest.fixture(scope="module")
def catalog():
    return YamlRepositoryCatalog(CATALOG).load()


def test_dois_projetos_e_quatro_repos_no_commit_fixado(catalog):
    assert [p.slug for p in catalog.projects] == ["phishforge", "phishing-quest"]
    assert catalog.repo_names == (
        "phishforge-api",
        "phishforge-frontend",
        "phishing-quest-api",
        "phishing_quest",
    )
    for spec in catalog.repos:
        assert len(spec.repo.commit) == 40, f"{spec.repo.name}: commit precisa ser o SHA inteiro"
        assert spec.repo.project in {p.slug for p in catalog.projects}


def test_stacks_dos_quatro_repos(catalog):
    assert {s.repo.name: s.repo.stack for s in catalog.repos} == {
        "phishforge-api": Stack.PYTHON_FASTAPI,
        "phishforge-frontend": Stack.TYPESCRIPT_REACT,
        "phishing-quest-api": Stack.GO_GIN,
        "phishing_quest": Stack.DART_FLUTTER,
    }


def test_quem_consome_quem_e_o_caminho_base_do_app(catalog):
    assert catalog.consumes == {
        "phishforge-frontend": ("phishforge-api",),
        "phishing_quest": ("phishing-quest-api",),
    }
    app = next(s for s in catalog.repos if s.repo.name == "phishing_quest")
    assert app.base_path == "/api/v1"


def test_ingestao_parcial_do_app_traz_so_a_api_dele(catalog):
    assert catalog.with_related(["phishing_quest"]) == ("phishing-quest-api", "phishing_quest")
    assert catalog.with_related(["phishforge-api"]) == ("phishforge-api", "phishforge-frontend")
