import subprocess
from collections.abc import Collection, Iterator
from datetime import datetime
from pathlib import Path

from engrama.application.ports.sources import SourceRepository, SourceTree
from engrama.application.ports.system import SecretScanner
from engrama.domain.entities import Repo


def _git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


class LocalSourceTree(SourceTree):
    """Arquivos versionados de um clone local. Ignora o que nao esta no git
    (build, node_modules) e o que a politica de segredos exclui."""

    def __init__(self, repo: Repo, root: Path, scanner: SecretScanner) -> None:
        self.repo = repo
        self._root = root
        self._scanner = scanner
        self._tracked = sorted(_git("ls-files", cwd=root).splitlines())

    @property
    def committed_at(self) -> datetime:
        return datetime.fromisoformat(_git("log", "-1", "--format=%cI", cwd=self._root))

    def files(self, suffixes: Collection[str], exclude_dirs: Collection[str] = ()) -> Iterator[str]:
        for path in self._tracked:
            parts = path.split("/")
            if not path.endswith(tuple(suffixes)):
                continue
            if any(part in exclude_dirs for part in parts[:-1]):
                continue
            if self._scanner.excludes(path):
                continue
            yield path

    def read(self, path: str) -> str:
        return (self._root / path).read_text(encoding="utf-8", errors="replace")


class GitSourceRepository(SourceRepository):
    """Clona em `cache_dir/repos/<nome>` e faz checkout do commit fixado."""

    def __init__(self, cache_dir: Path, scanner: SecretScanner) -> None:
        self._repos_dir = cache_dir / "repos"
        self._scanner = scanner

    def checkout(self, repo: Repo) -> SourceTree:
        root = self._repos_dir / repo.name
        if not root.exists():
            self._repos_dir.mkdir(parents=True, exist_ok=True)
            _git("clone", "--quiet", repo.url, str(root))
        try:
            _git("cat-file", "-e", f"{repo.commit}^{{commit}}", cwd=root)
        except subprocess.CalledProcessError:
            _git("fetch", "--quiet", "origin", cwd=root)
        _git("checkout", "--quiet", "--detach", repo.commit, cwd=root)
        return LocalSourceTree(repo, root, self._scanner)
