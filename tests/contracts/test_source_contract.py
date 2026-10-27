"""Contrato de SourceTree.

A mesma suite roda contra o fake em memoria e contra o `GitSourceRepository` real,
sobre um repositorio git local (sem rede). O ponto principal: a politica de
segredos vale para `files()` e tambem para `read()`, nos dois.
"""

from datetime import UTC, datetime

import pytest

from engrama.application.ports.sources import SourceTree
from engrama.domain.entities import Repo, Stack
from engrama.domain.errors import ExcludedSourcePath
from engrama.infrastructure.git.git_source_repository import GitSourceRepository
from engrama.infrastructure.security.secret_scanner import RegexSecretScanner
from tests.fakes.git_origin import make_origin
from tests.fakes.sources import InMemorySourceTree

FILES = {
    ".env": "SEGREDO=1",
    ".env.production": "SEGREDO=2",
    ".env.example": "SEGREDO=",
    "node_modules/x.ts": "export {}",
    "build/out.js": "var a",
    "assets/logo.png": "png",
    "app/main.py": "print(1)",
    "app/service.py": "x = 1",
    "docs/leia-me.md": "# oi",
}
VISIBLE = [".env.example", "app/main.py", "app/service.py", "docs/leia-me.md"]
EXCLUDED = [".env", ".env.production", "node_modules/x.ts", "build/out.js", "assets/logo.png"]
COMMITTED_AT = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
C = "a" * 40


@pytest.fixture(params=["memory", "git"])
def tree(request, tmp_path) -> SourceTree:
    scanner = RegexSecretScanner()
    if request.param == "memory":
        repo = Repo("contrato", "p", "https://x/contrato", C, Stack.PYTHON_FASTAPI)
        return InMemorySourceTree(repo, FILES, COMMITTED_AT, scanner)
    origin, (sha,) = make_origin(tmp_path, [FILES])
    repo = Repo("contrato", "p", str(origin), sha, Stack.PYTHON_FASTAPI)
    return GitSourceRepository(tmp_path / "cache", scanner).checkout(repo)


def test_lista_so_o_que_a_politica_permite(tree):
    assert sorted(tree.files(("",))) == VISIBLE


def test_filtra_por_extensao_e_por_diretorio(tree):
    assert sorted(tree.files((".py",))) == ["app/main.py", "app/service.py"]
    assert list(tree.files((".py",), exclude_dirs=("app",))) == []


def test_le_o_arquivo_permitido(tree):
    assert tree.read("app/main.py") == "print(1)"
    assert tree.read(".env.example") == "SEGREDO="


@pytest.mark.parametrize("path", EXCLUDED)
def test_recusa_ler_o_que_a_politica_exclui(tree, path):
    with pytest.raises(ExcludedSourcePath):
        tree.read(path)


@pytest.mark.parametrize("path", ["nao/existe.py", "../fora.py", "/etc/hosts"])
def test_so_le_arquivo_que_existe_na_arvore(tree, path):
    with pytest.raises(FileNotFoundError):
        tree.read(path)


def test_data_do_commit(tree):
    assert tree.committed_at == COMMITTED_AT
