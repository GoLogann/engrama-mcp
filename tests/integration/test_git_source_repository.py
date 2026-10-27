"""GitSourceRepository sobre um repositorio git local, sem rede."""

from engrama.domain.entities import Repo, Stack
from engrama.infrastructure.git.git_source_repository import GitSourceRepository
from engrama.infrastructure.security.secret_scanner import RegexSecretScanner
from tests.fakes.git_origin import make_origin


def repo_at(origin, sha) -> Repo:
    return Repo("alvo", "p", str(origin), sha, Stack.GO_GIN)


def test_checkout_usa_o_commit_fixado_e_nao_o_mais_recente(tmp_path):
    origin, (first, second) = make_origin(tmp_path, [{"a.go": "package a"}, {"b.go": "package b"}])
    sources = GitSourceRepository(tmp_path / "cache", RegexSecretScanner())

    old = sources.checkout(repo_at(origin, first))
    assert list(old.files((".go",))) == ["a.go"]

    new = sources.checkout(repo_at(origin, second))
    assert list(new.files((".go",))) == ["a.go", "b.go"]


def test_checkout_busca_commit_que_chegou_depois_do_clone(tmp_path):
    origin, (first,) = make_origin(tmp_path, [{"a.go": "package a"}])
    sources = GitSourceRepository(tmp_path / "cache", RegexSecretScanner())
    sources.checkout(repo_at(origin, first))  # clona

    import subprocess

    (origin / "c.go").write_text("package c")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    subprocess.run([*git, "add", "-A"], cwd=origin, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "terceiro"], cwd=origin, check=True)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=origin, check=True, capture_output=True, text=True
    ).stdout.strip()

    tree = sources.checkout(repo_at(origin, sha))

    assert "c.go" in tree.files((".go",))
