from collections.abc import Collection, Iterator, Mapping
from datetime import UTC, datetime

from engrama.application.dto.ingestion import Catalog
from engrama.application.ports.sources import RepositoryCatalog, SourceRepository, SourceTree
from engrama.application.ports.system import Clock, SecretScanner
from engrama.domain.entities import Repo
from engrama.domain.errors import ExcludedSourcePath

COMMITTED_AT = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


class InMemorySourceTree(SourceTree):
    """Arvore em memoria. Com `scanner`, aplica a mesma politica de segredos do adapter
    real (o contrato em tests/contracts/test_source_contract.py garante a equivalencia)."""

    def __init__(
        self,
        repo: Repo,
        files: Mapping[str, str],
        committed_at: datetime = COMMITTED_AT,
        scanner: SecretScanner | None = None,
    ):
        self.repo = repo
        self._files = dict(files)
        self._committed_at = committed_at
        self._scanner = scanner

    @property
    def committed_at(self) -> datetime:
        return self._committed_at

    def files(self, suffixes: Collection[str], exclude_dirs: Collection[str] = ()) -> Iterator[str]:
        for path in sorted(self._files):
            if self._excluded(path):
                continue
            if path.endswith(tuple(suffixes)) and not set(path.split("/")[:-1]) & set(exclude_dirs):
                yield path

    def read(self, path: str) -> str:
        if self._excluded(path):
            raise ExcludedSourcePath(path)
        if path not in self._files:
            raise FileNotFoundError(path)
        return self._files[path]

    def _excluded(self, path: str) -> bool:
        return self._scanner is not None and self._scanner.excludes(path)


class InMemorySourceRepository(SourceRepository):
    def __init__(self, trees: Mapping[str, Mapping[str, str]]):
        self._trees = trees
        self.checked_out: list[str] = []

    def checkout(self, repo: Repo) -> SourceTree:
        self.checked_out.append(repo.name)
        return InMemorySourceTree(repo, self._trees.get(repo.name, {}))


class StaticCatalog(RepositoryCatalog):
    def __init__(self, catalog: Catalog):
        self._catalog = catalog

    def load(self) -> Catalog:
        return self._catalog


class FixedClock(Clock):
    def __init__(self, moment: datetime = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)):
        self.moment = moment

    def now(self) -> datetime:
        return self.moment
