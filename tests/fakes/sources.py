from collections.abc import Collection, Iterator, Mapping
from datetime import UTC, datetime

from engrama.application.dto.ingestion import Catalog
from engrama.application.ports.sources import RepositoryCatalog, SourceRepository, SourceTree
from engrama.application.ports.system import Clock
from engrama.domain.entities import Repo

COMMITTED_AT = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


class InMemorySourceTree(SourceTree):
    def __init__(self, repo: Repo, files: Mapping[str, str], committed_at: datetime = COMMITTED_AT):
        self.repo = repo
        self._files = dict(files)
        self._committed_at = committed_at

    @property
    def committed_at(self) -> datetime:
        return self._committed_at

    def files(self, suffixes: Collection[str], exclude_dirs: Collection[str] = ()) -> Iterator[str]:
        for path in sorted(self._files):
            if path.endswith(tuple(suffixes)) and not set(path.split("/")[:-1]) & set(exclude_dirs):
                yield path

    def read(self, path: str) -> str:
        return self._files[path]


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
