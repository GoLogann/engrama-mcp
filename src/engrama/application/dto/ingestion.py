from dataclasses import dataclass
from datetime import datetime

from engrama.domain.entities import Project, Repo
from engrama.domain.services import MatchReport
from engrama.domain.value_objects.code_facts import (
    CallSite,
    DataStoreUse,
    DeclaredRoute,
    IssueReference,
)


@dataclass(frozen=True, slots=True)
class RepositorySpec:
    """Um repo do catalogo e o que nao sai do codigo dele: quem ele consome e
    o caminho base das chamadas (a base URL vem do ambiente)."""

    repo: Repo
    consumes: tuple[str, ...] = ()
    base_path: str = ""


@dataclass(frozen=True, slots=True)
class Catalog:
    projects: tuple[Project, ...]
    repos: tuple[RepositorySpec, ...]

    def project_of(self, spec: RepositorySpec) -> Project:
        return next(p for p in self.projects if p.slug == spec.repo.project)

    @property
    def repo_names(self) -> tuple[str, ...]:
        return tuple(spec.repo.name for spec in self.repos)

    @property
    def consumes(self) -> dict[str, tuple[str, ...]]:
        return {spec.repo.name: spec.consumes for spec in self.repos if spec.consumes}


@dataclass(frozen=True, slots=True)
class CodeFacts:
    """O que os extratores acharam num repo. `diagnostics` registra o que eles
    viram e nao souberam interpretar, para nada sumir em silencio."""

    modules: frozenset[str] = frozenset()
    routes: tuple[DeclaredRoute, ...] = ()
    calls: tuple[CallSite, ...] = ()
    datastores: tuple[DataStoreUse, ...] = ()
    issues: tuple[IssueReference, ...] = ()
    diagnostics: tuple[str, ...] = ()

    def merged(self, other: "CodeFacts") -> "CodeFacts":
        return CodeFacts(
            modules=self.modules | other.modules,
            routes=self.routes + other.routes,
            calls=self.calls + other.calls,
            datastores=self.datastores + other.datastores,
            issues=self.issues + other.issues,
            diagnostics=self.diagnostics + other.diagnostics,
        )


@dataclass(frozen=True, slots=True)
class RepositoryFacts:
    spec: RepositorySpec
    committed_at: datetime
    facts: CodeFacts


@dataclass(frozen=True, slots=True)
class RepositorySummary:
    name: str
    commit: str
    modules: int
    routes: int
    calls: int
    datastores: int
    issues: int


@dataclass(frozen=True, slots=True)
class IngestionReport:
    repos: tuple[RepositorySummary, ...]
    links: MatchReport
    diagnostics: tuple[str, ...] = ()
