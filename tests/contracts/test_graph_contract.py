"""Contrato de GraphWriter + StructureReader.

A mesma suite roda contra o fake em memoria e contra o Neo4j real
(substituicao de Liskov): se o fake passa e o Neo4j nao, o fake mente e os
testes de caso de uso nao valem. Os testes no Neo4j usam chaves com o
prefixo `contract-` e as apagam no fim; sem Neo4j acessivel, sao pulados.
"""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from engrama.domain.entities import Project, Repo, Stack
from engrama.domain.services import RouteMatch, StructuralGraphBuilder
from engrama.domain.value_objects import Evidence, HttpMethod, HttpRoute, Validity
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


@pytest.fixture(params=["memory", pytest.param("neo4j", marks=pytest.mark.integration)])
def graph(request):
    if request.param == "memory":
        fake = InMemoryGraph()
        yield fake, fake
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
    yield writer, Neo4jStructureReader(driver)
    driver.execute_query(cleanup)
    resource.close()


def own_routes(reader):
    return sorted(r for r in reader.routes() if r.repo in REPOS)


def own_calls(reader):
    return sorted(c for c in reader.calls() if c.repo in REPOS)


def test_grava_e_le_rotas_e_chamadas(graph):
    writer, reader = graph

    writer.write(graphs([ITEMS, RANKING]), run_id="r1", at=T0)

    assert [(r.line, r.route) for r in own_routes(reader)] == [
        (10, "GET /api/v1/items/{id}"),
        (11, "GET /api/v1/rankings"),
    ]
    (call,) = own_calls(reader)
    assert (call.path, call.line, call.shape, call.target) == (
        "lib/data/items.dart",
        7,
        "GET /api/v1/items/{}",
        API.name,
    )


def test_regravar_nao_duplica(graph):
    writer, reader = graph

    writer.write(graphs([ITEMS, RANKING]), run_id="r1", at=T0)
    writer.write(graphs([ITEMS, RANKING], at=T1), run_id="r2", at=T1)

    assert len(own_routes(reader)) == 2
    assert len(own_calls(reader)) == 1


def test_fato_que_sumiu_deixa_de_valer(graph):
    writer, reader = graph
    writer.write(graphs([ITEMS, RANKING]), run_id="r1", at=T0)

    writer.write(graphs([ITEMS], with_call=False, at=T1), run_id="r2", at=T1)

    assert [r.route for r in own_routes(reader)] == ["GET /api/v1/items/{id}"]
    assert own_calls(reader) == []


def test_so_aposenta_arestas_dos_donos_regravados(graph):
    writer, reader = graph
    writer.write(graphs([ITEMS, RANKING]), run_id="r1", at=T0)

    only_api = {API.name: graphs([ITEMS, RANKING], at=T1)[API.name]}
    writer.write(only_api, run_id="r2", at=T1)

    assert len(own_calls(reader)) == 1
