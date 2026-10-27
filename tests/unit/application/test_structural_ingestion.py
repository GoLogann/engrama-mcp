from engrama.application.dto.ingestion import Catalog, RepositorySpec
from engrama.application.dto.structure_check import CallFact, GroundTruth, RouteFact
from engrama.application.ports.graph import GroundTruthSource
from engrama.application.use_cases.build_structural_graph import BuildStructuralGraph
from engrama.application.use_cases.check_structure import CheckStructureAgainstGroundTruth
from engrama.application.use_cases.ingest_repository import IngestRepository
from engrama.application.use_cases.link_calls_to_routes import LinkCallsToRoutes
from engrama.domain.entities import EdgeKind, Project, Repo, Stack
from engrama.domain.services import RouteNormalizer, StructuralGraphBuilder
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
) -> BuildStructuralGraph:
    normalizer = RouteNormalizer()
    builder = StructuralGraphBuilder()
    extractors = [FastApiExtractor(normalizer), ReactServiceExtractor(normalizer)]
    return BuildStructuralGraph(
        catalog=StaticCatalog(CATALOG),
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


def test_ingestao_parcial_so_toca_os_repos_pedidos():
    trees = {"forge-api": API_FILES, "forge-front": FRONT_FILES}
    sources = InMemorySourceRepository(trees)

    make(trees, InMemoryGraph(), sources=sources).execute(only=["forge-api"])

    assert sources.checked_out == ["forge-api"]


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
