import pytest

from engrama.application.dto.ingestion import Catalog, RepositorySpec
from engrama.application.dto.structure_check import CallFact, DataStoreFact, GroundTruth, RouteFact
from engrama.application.ports.graph import GroundTruthSource
from engrama.application.use_cases.build_structural_graph import BuildStructuralGraph
from engrama.application.use_cases.check_structure import CheckStructureAgainstGroundTruth
from engrama.application.use_cases.ingest_repository import IngestRepository
from engrama.application.use_cases.link_calls_to_routes import LinkCallsToRoutes
from engrama.domain.entities import EdgeKind, Project, Repo, Stack
from engrama.domain.errors import UnknownRepository
from engrama.domain.services import RouteNormalizer, StructuralGraphBuilder
from engrama.domain.value_objects import Evidence, Validity
from engrama.domain.value_objects.code_facts import DataStoreUse
from engrama.infrastructure.extractors import FastApiExtractor, ReactServiceExtractor
from tests.fakes.graph import InMemoryGraph
from tests.fakes.sources import COMMITTED_AT, FixedClock, InMemorySourceRepository, StaticCatalog

C = "d" * 40
API = Repo("forge-api", "forge", "https://x/forge-api", C, Stack.PYTHON_FASTAPI)
FRONT = Repo("forge-front", "forge", "https://x/forge-front", C, Stack.TYPESCRIPT_REACT)
CATALOG = Catalog(
    projects=(Project("forge", "Forge"),),
    repos=(RepositorySpec(API), RepositorySpec(FRONT, consumes=("forge-api",))),
)
API_FILES = {
    "app/api.py": (
        'router = APIRouter(prefix="/api/v1")\n'
        '@router.get("/emails/{email_id}")\ndef ler(email_id): ...\n'
        '@router.get("/cues")\ndef cues(): ...\n'
    )
}
FRONT_FILES = {
    "src/services/api.ts": "export const ler = (id) => request(`/api/v1/emails/${id}`)\n"
}


def make(
    trees,
    graph: InMemoryGraph,
    clock: FixedClock | None = None,
    sources: InMemorySourceRepository | None = None,
    catalog: Catalog = CATALOG,
) -> BuildStructuralGraph:
    normalizer = RouteNormalizer()
    builder = StructuralGraphBuilder()
    extractors = [FastApiExtractor(normalizer), ReactServiceExtractor(normalizer)]
    return BuildStructuralGraph(
        catalog=StaticCatalog(catalog),
        ingest=IngestRepository(sources or InMemorySourceRepository(trees), extractors),
        link=LinkCallsToRoutes(builder),
        builder=builder,
        writer=graph,
        clock=clock or FixedClock(),
    )


def test_ingestao_grava_estrutura_e_casa_chamadas_entre_repos():
    graph = InMemoryGraph()

    report = make({"forge-api": API_FILES, "forge-front": FRONT_FILES}, graph).execute()

    assert graph.schema_ready
    assert [(r.name, r.routes, r.calls) for r in report.repos] == [
        ("forge-api", 2, 0),
        ("forge-front", 0, 1),
    ]
    assert [str(r.route) for r in report.links.routes_without_callers] == ["GET /api/v1/cues"]
    (calls,) = graph.open_edges(EdgeKind.CALLS)
    assert calls.owner == "forge-front"
    assert calls.edge.validity.valid_from == COMMITTED_AT
    assert graph.calls() == [
        CallFact("forge-front", "src/services/api.ts", 1, "GET /api/v1/emails/{}", "forge-api")
    ]


def test_rota_removida_deixa_de_valer_na_reingestao():
    graph = InMemoryGraph()
    make({"forge-api": API_FILES, "forge-front": FRONT_FILES}, graph).execute()

    later = FixedClock()
    later.moment = later.moment.replace(day=29)
    without_cues = {"app/api.py": API_FILES["app/api.py"].split('@router.get("/cues")')[0]}
    make({"forge-api": without_cues, "forge-front": FRONT_FILES}, graph, later).execute()

    open_routes = [r.route for r in graph.routes()]
    closed = [s for s in graph.edges if not s.open]
    assert open_routes == ["GET /api/v1/emails/{email_id}"]
    assert [(s.edge.kind, s.valid_to) for s in closed] == [(EdgeKind.EXPOSES, later.moment)]


def test_ingestao_parcial_do_cliente_mantem_as_chamadas_abertas():
    graph = InMemoryGraph()
    trees = {"forge-api": API_FILES, "forge-front": FRONT_FILES}
    make(trees, graph).execute()

    later = FixedClock()
    later.moment = later.moment.replace(day=29)
    report = make(trees, graph, later).execute(only=["forge-front"])

    assert len(graph.calls()) == 1
    assert [s for s in graph.edges if not s.open] == []
    assert report.related == ("forge-api",)


def test_ingestao_parcial_so_toca_os_repos_relacionados():
    docs = RepositorySpec(Repo("forge-docs", "forge", "https://x/forge-docs", C, Stack.GO_GIN))
    catalog = Catalog(CATALOG.projects, (*CATALOG.repos, docs))
    trees = {"forge-api": API_FILES, "forge-front": FRONT_FILES}
    sources = InMemorySourceRepository(trees)

    report = make(trees, InMemoryGraph(), sources=sources, catalog=catalog).execute(
        only=["forge-api"]
    )

    assert sources.checked_out == ["forge-api", "forge-front"]
    assert report.related == ("forge-front",)


def test_repo_desconhecido_e_recusado_antes_de_ler_qualquer_coisa():
    trees = {"forge-api": API_FILES}
    sources = InMemorySourceRepository(trees)

    with pytest.raises(UnknownRepository):
        make(trees, InMemoryGraph(), sources=sources).execute(only=["forge-apii"])

    assert sources.checked_out == []


class StaticGroundTruth(GroundTruthSource):
    def __init__(self, truth: GroundTruth):
        self._truth = truth

    def load(self) -> GroundTruth:
        return self._truth


def test_conferencia_aponta_o_que_falta_e_o_que_sobra():
    graph = InMemoryGraph()
    make({"forge-api": API_FILES, "forge-front": FRONT_FILES}, graph).execute()
    expected = GroundTruth(
        routes=frozenset(
            {
                RouteFact("forge-api", "app/api.py", 2, "GET /api/v1/emails/{email_id}"),
                RouteFact("forge-api", "app/api.py", 9, "POST /api/v1/generate"),
            }
        ),
        calls=frozenset(graph.calls()),
    )

    report = CheckStructureAgainstGroundTruth(graph, StaticGroundTruth(expected)).execute()

    assert not report.passed
    assert [r.route for r in report.missing_routes] == ["POST /api/v1/generate"]
    assert [r.route for r in report.unexpected_routes] == ["GET /api/v1/cues"]
    assert report.call_coverage == 1.0


def test_conferencia_de_bancos_aponta_o_que_falta_e_o_que_sobra():
    graph = InMemoryGraph()
    store = DataStoreUse(
        "forge-api",
        "qdrant",
        "phishing_articles",
        (Evidence.in_code("forge-api", "docker-compose.yml", C, 26),),
    )
    validity = Validity.starting(COMMITTED_AT)
    graph.write(
        {
            "forge-api": StructuralGraphBuilder().repository(
                Project("forge", "Forge"), API, [], [], [store], [], validity
            )
        },
        run_id="r1",
        at=COMMITTED_AT,
    )
    expected = GroundTruth(
        routes=frozenset(),
        calls=frozenset(),
        datastores=frozenset(
            {
                DataStoreFact("forge-api", "qdrant", "phishing_articles"),
                DataStoreFact("forge-api", "postgres", "forge"),
            }
        ),
    )

    report = CheckStructureAgainstGroundTruth(graph, StaticGroundTruth(expected)).execute()

    assert [d.name for d in report.missing_datastores] == ["forge"]
    assert report.unexpected_datastores == ()
    assert report.datastore_coverage == 0.5
    assert not report.passed
