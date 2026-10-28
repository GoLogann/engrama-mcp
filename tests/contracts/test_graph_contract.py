"""Contrato de GraphWriter + StructureReader.

A mesma suite roda contra o fake em memoria e contra o Neo4j real
(substituicao de Liskov): se o fake passa e o Neo4j nao, o fake mente e os
testes de caso de uso nao valem. Os testes no Neo4j usam chaves com o
prefixo `contract-` e as apagam no fim; sem Neo4j acessivel, sao pulados.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime

import pytest

from engrama.application.ports.graph import GraphWriter, StructureReader
from engrama.domain.entities import Doc, Edge, EdgeKind, Endpoint, Project, Repo, Stack
from engrama.domain.services import RouteMatch, StructuralGraphBuilder
from engrama.domain.value_objects import Evidence, HttpMethod, HttpRoute, Provenance, Validity
from engrama.domain.value_objects.code_facts import CallSite, DeclaredRoute
from tests.fakes.graph import InMemoryGraph

C = "e" * 40
T0 = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)
T1 = datetime(2026, 10, 29, 9, 0, tzinfo=UTC)
PROJECT = Project("contract-project", "Contrato")
API = Repo("contract-api", "contract-project", "https://x/contract-api", C, Stack.GO_GIN)
FRONT = Repo(
    "contract-front", "contract-project", "https://x/contract-front", C, Stack.DART_FLUTTER
)
REPOS = {API.name, FRONT.name}


def declared(path: str, line: int) -> DeclaredRoute:
    return DeclaredRoute(
        API.name,
        "router",
        HttpRoute(HttpMethod.GET, path),
        Evidence.in_code(API.name, "router/r.go", C, line),
    )


ITEMS = declared("/api/v1/items/{id}", 10)
RANKING = declared("/api/v1/rankings", 11)
CALL = CallSite(
    FRONT.name,
    "lib/data",
    HttpRoute(HttpMethod.GET, "/api/v1/items/{itemId}"),
    Evidence.in_code(FRONT.name, "lib/data/items.dart", C, 7),
)


def graphs(routes, with_call=True, at=T0):
    builder = StructuralGraphBuilder()
    validity = Validity.starting(T0, ingested_at=at)
    api = builder.repository(PROJECT, API, ["router"], routes, [], [], validity)
    front = builder.repository(PROJECT, FRONT, ["lib/data"], [], [], [], validity)
    if with_call:
        calls = builder.calls([RouteMatch(CALL, ITEMS)], validity)
        front = replace(front, edges=front.edges + calls)
    return {API.name: api, FRONT.name: front}


@dataclass(frozen=True)
class EdgeTimes:
    open: bool
    valid_from: datetime
    ingested_at: datetime
    valid_to: datetime | None


@dataclass(frozen=True)
class Backend:
    writer: GraphWriter
    reader: StructureReader
    # Tempos das arestas de um tipo (ex.: "EXPOSES") que apontam para dados do contrato.
    # A porta de leitura nao os expoe, entao cada backend os le do seu jeito.
    edge_times: Callable[[str], list[EdgeTimes]]


def _memory_backend() -> Backend:
    fake = InMemoryGraph()

    def edge_times(kind: str) -> list[EdgeTimes]:
        return [
            EdgeTimes(s.open, s.edge.validity.valid_from, s.edge.validity.ingested_at, s.valid_to)
            for s in fake.edges
            if s.edge.kind.value == kind and s.edge.target.key.startswith("contract-")
        ]

    return Backend(fake, fake, edge_times)


@pytest.fixture(params=["memory", pytest.param("neo4j", marks=pytest.mark.integration)])
def backend(request):
    if request.param == "memory":
        yield _memory_backend()
        return

    from engrama.bootstrap.settings import Settings
    from engrama.infrastructure.neo4j.connection import open_driver
    from engrama.infrastructure.neo4j.graph_writer import Neo4jGraphWriter
    from engrama.infrastructure.neo4j.structure_reader import Neo4jStructureReader

    settings = Settings()
    resource = open_driver(
        settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password.get_secret_value()
    )
    driver = next(resource)
    try:
        driver.verify_connectivity()
    except Exception as error:  # pragma: no cover - depende do ambiente
        pytest.skip(f"Neo4j indisponivel: {error}")
    cleanup = "MATCH (n) WHERE n.key STARTS WITH 'contract-' DETACH DELETE n"
    driver.execute_query(cleanup)
    writer = Neo4jGraphWriter(driver)
    writer.ensure_schema()

    def edge_times(kind: str) -> list[EdgeTimes]:
        records, _, _ = driver.execute_query(
            f"MATCH ()-[r:{kind}]->(t) WHERE t.key STARTS WITH 'contract-' "
            "RETURN r.open AS open, r.valid_from AS valid_from, "
            "r.ingested_at AS ingested_at, r.valid_to AS valid_to"
        )
        return [
            EdgeTimes(
                row["open"],
                row["valid_from"].to_native(),
                row["ingested_at"].to_native(),
                row["valid_to"].to_native() if row["valid_to"] else None,
            )
            for row in records
        ]

    yield Backend(writer, Neo4jStructureReader(driver), edge_times)
    driver.execute_query(cleanup)
    resource.close()


def own_routes(reader):
    return sorted(r for r in reader.routes() if r.repo in REPOS)


def own_calls(reader):
    return sorted(c for c in reader.calls() if c.repo in REPOS)


def test_grava_e_le_rotas_e_chamadas(backend):
    backend.writer.write(graphs([ITEMS, RANKING]), run_id="r1", at=T0)

    assert [(r.line, r.route) for r in own_routes(backend.reader)] == [
        (10, "GET /api/v1/items/{id}"),
        (11, "GET /api/v1/rankings"),
    ]
    (call,) = own_calls(backend.reader)
    assert (call.path, call.line, call.shape, call.target) == (
        "lib/data/items.dart",
        7,
        "GET /api/v1/items/{}",
        API.name,
    )


def test_regravar_nao_duplica(backend):
    backend.writer.write(graphs([ITEMS, RANKING]), run_id="r1", at=T0)
    backend.writer.write(graphs([ITEMS, RANKING], at=T1), run_id="r2", at=T1)

    assert len(own_routes(backend.reader)) == 2
    assert len(own_calls(backend.reader)) == 1


def test_valid_from_e_ingested_at_guardam_a_primeira_vez(backend):
    backend.writer.write(graphs([ITEMS, RANKING]), run_id="r1", at=T0)
    backend.writer.write(graphs([ITEMS, RANKING], at=T1), run_id="r2", at=T1)

    times = backend.edge_times("EXPOSES")

    assert len(times) == 2
    assert {(t.open, t.valid_from, t.ingested_at) for t in times} == {(True, T0, T0)}


def test_fato_que_sumiu_deixa_de_valer(backend):
    backend.writer.write(graphs([ITEMS, RANKING]), run_id="r1", at=T0)

    backend.writer.write(graphs([ITEMS], with_call=False, at=T1), run_id="r2", at=T1)

    assert [r.route for r in own_routes(backend.reader)] == ["GET /api/v1/items/{id}"]
    assert own_calls(backend.reader) == []
    closed = [t for t in backend.edge_times("EXPOSES") if not t.open]
    assert [t.valid_to for t in closed] == [T1]


def test_so_aposenta_arestas_dos_donos_regravados(backend):
    backend.writer.write(graphs([ITEMS, RANKING]), run_id="r1", at=T0)

    only_api = {API.name: graphs([ITEMS, RANKING], at=T1)[API.name]}
    backend.writer.write(only_api, run_id="r2", at=T1)

    assert len(own_calls(backend.reader)) == 1


def test_chamada_sem_destino_fecha_quando_a_rota_some_so_na_api(backend):
    backend.writer.write(graphs([ITEMS, RANKING]), run_id="r1", at=T0)

    only_api = {API.name: graphs([RANKING], at=T1)[API.name]}
    backend.writer.write(only_api, run_id="r2", at=T1)

    assert own_calls(backend.reader) == []
    (call,) = backend.edge_times("CALLS")
    assert (call.open, call.valid_to) == (False, T1)


def test_aresta_com_ponta_que_nao_existe_nao_e_gravada(backend):
    """A escrita casa as duas pontas: aresta para um no que o grafo nao tem nao
    grava nada. E o que sustenta a camada de documentacao nao regravar o no do
    endpoint (ADR 0010) — ela so cria aresta para endpoint que leu do grafo."""
    builder = StructuralGraphBuilder()
    validity = Validity.starting(T0)
    orphan = Edge(
        EdgeKind.DOCUMENTED_IN,
        Endpoint(API.name, HttpRoute(HttpMethod.GET, "/api/v1/nao-existe")).ref,
        Doc(API.name, "contract-README.md", "Contrato").ref,
        Provenance.extracted(Evidence.in_code(API.name, "contract-README.md", C, 1)),
        validity,
    )
    graph = builder.repository(PROJECT, API, ["router"], [ITEMS], [], [], validity)

    backend.writer.write(
        {API.name: replace(graph, edges=(*graph.edges, orphan))}, run_id="r1", at=T0
    )

    assert [(r.line, r.route) for r in own_routes(backend.reader)] == [
        (10, "GET /api/v1/items/{id}")
    ]
    assert backend.edge_times("DOCUMENTED_IN") == []
