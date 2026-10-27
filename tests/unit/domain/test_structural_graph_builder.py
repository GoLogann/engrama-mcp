from datetime import UTC, datetime

from engrama.domain.entities import (
    DataStoreKind,
    EdgeKind,
    Module,
    Project,
    Repo,
    Stack,
)
from engrama.domain.services import RouteMatch, StructuralGraphBuilder
from engrama.domain.value_objects import Evidence, HttpMethod, HttpRoute, NodeKind, Source, Validity
from engrama.domain.value_objects.code_facts import (
    CallSite,
    DataStoreUse,
    DeclaredRoute,
    IssueReference,
)

C = "b" * 40
PROJECT = Project("forge", "Forge")
API = Repo("forge-api", "forge", "https://github.com/x/forge-api", C, Stack.PYTHON_FASTAPI)
VALIDITY = Validity.starting(datetime(2026, 10, 1, tzinfo=UTC))
ROUTE = DeclaredRoute(
    "forge-api",
    "app/api/v1/endpoints",
    HttpRoute(HttpMethod.POST, "/api/v1/generate"),
    Evidence.in_code("forge-api", "app/api/v1/endpoints/generator.py", C, 50),
    handler="generate",
)


def build(**overrides):
    args = {
        "project": PROJECT,
        "repo": API,
        "modules": ["app/api/v1/endpoints"],
        "routes": [ROUTE],
        "datastores": [],
        "issues": [],
        "validity": VALIDITY,
    }
    return StructuralGraphBuilder().repository(**(args | overrides))


def edges_of(graph, kind):
    return [(str(e.source), str(e.target)) for e in graph.edges if e.kind is kind]


def test_hierarquia_de_modulos_ate_o_repo_e_o_projeto():
    graph = build()

    assert edges_of(graph, EdgeKind.PART_OF) == [
        ("Repo(forge-api)", "Project(forge)"),
        ("Module(forge-api:app)", "Repo(forge-api)"),
        ("Module(forge-api:app/api)", "Module(forge-api:app)"),
        ("Module(forge-api:app/api/v1)", "Module(forge-api:app/api)"),
        ("Module(forge-api:app/api/v1/endpoints)", "Module(forge-api:app/api/v1)"),
    ]


def test_modulo_da_raiz_pertence_ao_repo():
    graph = build(modules=["."], routes=[])

    assert ("Module(forge-api:.)", "Repo(forge-api)") in edges_of(graph, EdgeKind.PART_OF)


def test_repo_pertence_ao_projeto_com_o_repo_no_commit_fixado_como_evidencia():
    graph = build(modules=[], routes=[])

    (edge,) = [e for e in graph.edges if str(e.source) == "Repo(forge-api)"]

    assert str(edge.provenance.evidence[0]) == f"https://github.com/x/forge-api/tree/{C}"


def test_rota_vira_endpoint_exposto_pelo_modulo():
    graph = build()

    assert edges_of(graph, EdgeKind.EXPOSES) == [
        ("Module(forge-api:app/api/v1/endpoints)", "Endpoint(forge-api:POST /api/v1/generate)")
    ]
    assert all(e.provenance.source is Source.EXTRACTION for e in graph.edges)


def test_banco_e_issues_com_evidencias_agrupadas():
    compose = Evidence.in_code("forge-api", "docker-compose.yml", C, 2)
    first = Evidence.in_code("forge-api", "app/main.py", C, 3)
    second = Evidence.in_code("forge-api", "app/main.py", C, 9)
    graph = build(
        modules=["app"],
        routes=[],
        datastores=[DataStoreUse("forge-api", "postgres", "forge", (compose,))],
        issues=[
            IssueReference("forge-api", "app", "forge-api", 7, first),
            IssueReference("forge-api", "app", "forge-api", 7, second),
        ],
    )

    stores = [e for e in graph.edges if e.kind is EdgeKind.STORES_IN]
    issues = [e for e in graph.edges if e.kind is EdgeKind.REFERENCES_ISSUE]
    assert stores[0].target.key == f"forge-api:{DataStoreKind.POSTGRES}:forge"
    assert len(issues) == 1
    assert issues[0].provenance.evidence == (first, second)


def test_calls_leva_evidencia_dos_dois_lados():
    call = CallSite(
        "forge-front",
        "src/services",
        HttpRoute(HttpMethod.POST, "/api/v1/generate"),
        Evidence.in_code("forge-front", "src/services/apiService.ts", C, 15),
    )

    (edge,) = StructuralGraphBuilder().calls([RouteMatch(call, ROUTE)], VALIDITY)

    assert edge.source == Module("forge-front", "src/services").ref
    assert edge.target.kind is NodeKind.ENDPOINT
    assert edge.provenance.evidence == (call.evidence, ROUTE.evidence)
