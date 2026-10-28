from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from engrama.domain.entities import Project, Repo
from engrama.domain.errors import UnknownRepository
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

    def only(self, names: Iterable[str]) -> tuple[str, ...]:
        """Os repos pedidos, na ordem do catalogo. Sem `names`, o catalogo
        inteiro; um nome fora dele e recusado em vez de ignorado."""
        requested = set(names)
        if not requested:
            return self.repo_names
        unknown = requested - set(self.repo_names)
        if unknown:
            raise UnknownRepository(
                f"repo fora do catalogo: {', '.join(sorted(unknown))} "
                f"(catalogo: {', '.join(self.repo_names)})"
            )
        return tuple(name for name in self.repo_names if name in requested)

    def with_related(self, names: Iterable[str]) -> tuple[str, ...]:
        """Os repos a ingerir para que uma ingestao parcial continue correta.

        Uma CALLS so existe se o cliente e o servidor estao na mesma rodada: o
        cliente e o dono da aresta, e ela e fechada quando a rodada nao a
        reencontra. Por isso entram, alem dos pedidos, (1) os clientes de cada
        pedido, cujas chamadas dependem das rotas que podem ter mudado, e (2)
        todos os servidores de cada repo que entrou, ate nao faltar nenhum.
        Sem `names`, vale o catalogo inteiro. Devolve na ordem do catalogo.
        """
        requested = set(self.only(names))
        consumes = self.consumes
        selected = requested | {
            client for client, servers in consumes.items() if requested & set(servers)
        }
        while missing := {s for name in selected for s in consumes.get(name, ())} - selected:
            selected |= missing
        return tuple(name for name in self.repo_names if name in selected)

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
    # Repos que entraram na rodada so por serem clientes ou servidores dos pedidos.
    related: tuple[str, ...] = ()
