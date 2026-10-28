import uuid
from collections.abc import Collection

from engrama.application.dto.ingestion import IngestionReport, RepositorySummary
from engrama.application.ports.graph import GraphWriter
from engrama.application.ports.sources import RepositoryCatalog
from engrama.application.ports.system import Clock
from engrama.application.use_cases.ingest_repository import IngestRepository
from engrama.application.use_cases.link_calls_to_routes import LinkCallsToRoutes
from engrama.domain.services import RepositoryGraph, StructuralGraphBuilder
from engrama.domain.value_objects import Validity


class BuildStructuralGraph:
    """Monta e grava a camada de estrutura de todos os repos do catalogo.

    As chamadas so casam depois que todos os repos foram extraidos, porque o
    cliente e a API estao em repos diferentes.
    """

    def __init__(
        self,
        catalog: RepositoryCatalog,
        ingest: IngestRepository,
        link: LinkCallsToRoutes,
        builder: StructuralGraphBuilder,
        writer: GraphWriter,
        clock: Clock,
    ) -> None:
        self._catalog = catalog
        self._ingest = ingest
        self._link = link
        self._builder = builder
        self._writer = writer
        self._clock = clock

    def execute(self, only: Collection[str] = ()) -> IngestionReport:
        catalog = self._catalog.load()
        now = self._clock.now()
        names = catalog.with_related(only)
        specs = [s for s in catalog.repos if s.repo.name in names]
        repositories = [self._ingest.execute(spec) for spec in specs]

        graphs: dict[str, RepositoryGraph] = {}
        for repository in repositories:
            facts = repository.facts
            graphs[repository.spec.repo.name] = self._builder.repository(
                project=catalog.project_of(repository.spec),
                repo=repository.spec.repo,
                modules=facts.modules,
                routes=facts.routes,
                datastores=facts.datastores,
                issues=facts.issues,
                validity=Validity.starting(repository.committed_at, ingested_at=now),
            )

        links = self._link.execute(repositories, catalog.consumes, now)
        for caller, edges in links.edges_by_caller.items():
            graphs[caller] = graphs[caller].merged(RepositoryGraph(edges=edges))

        self._writer.ensure_schema()
        self._writer.write(graphs, run_id=uuid.uuid4().hex, at=now)

        return IngestionReport(
            repos=tuple(
                RepositorySummary(
                    name=r.spec.repo.name,
                    commit=r.spec.repo.commit,
                    modules=len(r.facts.modules),
                    routes=len(r.facts.routes),
                    calls=len(r.facts.calls),
                    datastores=len(r.facts.datastores),
                    issues=len(r.facts.issues),
                )
                for r in repositories
            ),
            links=links.report,
            diagnostics=tuple(d for r in repositories for d in r.facts.diagnostics)
            + tuple(
                f"{caller} chama {target} e o catalogo nao declara: "
                f"acrescente `consumes: [{target}]` em config/repos.yaml"
                for caller, target in links.undeclared
            ),
            related=tuple(n for n in names if only and n not in only),
        )
