"""Contrato de GraphReader.

A mesma suite roda contra o leitor em memoria e contra o do Neo4j. Os dois nao
ordenam igual em todo caso (so o Neo4j tem o CASE de rotulo no banco), entao o
contrato cobra o que os dois precisam garantir: achar pelo nome, respeitar o
limite, nunca devolver no que nao existe, dizer a direcao de verdade de cada
aresta e carregar a evidencia.

Os testes no Neo4j usam chaves com o prefixo `contract-` e as apagam no fim;
sem Neo4j acessivel, sao pulados.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from engrama.application.dto.consulta import Direction, NodeSummary
from engrama.application.ports.graph import GraphReader, GraphWriter
from engrama.domain.entities import Project, Repo, Stack
from engrama.domain.services import StructuralGraphBuilder
from engrama.domain.value_objects import (
    Evidence,
    HttpMethod,
    HttpRoute,
    NodeKind,
    NodeRef,
    Validity,
)
from engrama.domain.value_objects.code_facts import DataStoreUse, DeclaredRoute
from tests.fakes.graph import InMemoryGraph
from tests.fakes.reader import InMemoryReader

C = "e" * 40
T0 = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)
PROJECT = Project("contract-proj", "Contrato")
API = Repo("contract-api", "contract-proj", "https://x/contract-api", C, Stack.PYTHON_FASTAPI)
ROTA = HttpRoute(HttpMethod.GET, "/api/v1/itens")
MODULO = "app/api"
ROUTE = DeclaredRoute(API.name, MODULO, ROTA, Evidence.in_code(API.name, "app/api/itens.py", C, 14))
BANCO = DataStoreUse(
    API.name,
    "postgres",
    "contrato",
    (Evidence.in_code(API.name, "docker-compose.yml", C, 9),),
)

ENDPOINT = NodeRef(NodeKind.ENDPOINT, f"{API.name}:GET /api/v1/itens")
MODULE = NodeRef(NodeKind.MODULE, f"{API.name}:{MODULO}")
DATASTORE = NodeRef(NodeKind.DATASTORE, f"{API.name}:postgres:contrato")
REPO_REF = NodeRef(NodeKind.REPO, API.name)


def graph():
    builder = StructuralGraphBuilder()
    return {
        API.name: builder.repository(
            project=PROJECT,
            repo=API,
            modules=[MODULO],
            routes=[ROUTE],
            datastores=[BANCO],
            issues=[],
            validity=Validity.starting(T0),
        )
    }


@dataclass(frozen=True)
class Backend:
    writer: GraphWriter
    reader: GraphReader


@pytest.fixture(params=["memory", pytest.param("neo4j", marks=pytest.mark.integration)])
def backend(request):
    written = graph()
    if request.param == "memory":
        fake = InMemoryGraph()
        fake.write(written, run_id="r1", at=T0)
        nodes, edges = _fake_view(written)
        yield Backend(fake, InMemoryReader(nodes=nodes, edges=edges))
        return

    from engrama.bootstrap.settings import Settings
    from engrama.infrastructure.neo4j.connection import open_driver
    from engrama.infrastructure.neo4j.graph_reader import Neo4jGraphReader
    from engrama.infrastructure.neo4j.graph_writer import Neo4jGraphWriter

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
    writer.write(written, run_id="r1", at=T0)
    yield Backend(writer, Neo4jGraphReader(driver))
    driver.execute_query(cleanup)
    resource.close()


def _fake_view(written):
    """Traduz o grafo escrito para o que o leitor em memoria consome."""
    from engrama.application.dto.consulta import Connection

    rotulos = {
        NodeKind.PROJECT: lambda n: n.name,
        NodeKind.REPO: lambda n: n.name,
        NodeKind.MODULE: lambda n: n.path,
        NodeKind.ENDPOINT: lambda n: str(n.route),
        NodeKind.DATASTORE: lambda n: f"{n.store_kind} {n.name}",
    }
    arquivos = (NodeKind.MODULE, NodeKind.DOC, NodeKind.DECISION, NodeKind.CHUNK)
    resumos: dict[NodeRef, NodeSummary] = {}
    for one in next(iter(written.values())).nodes:
        repo = getattr(one, "repo", "") or getattr(one, "name", "")
        caminho = getattr(one, "path", None) if one.node_kind in arquivos else None
        resumos[one.ref] = NodeSummary(
            ref=one.ref,
            label=rotulos.get(one.node_kind, lambda n: n.key)(one),
            repo=repo,
            source=f"{repo}/{caminho}" if repo and caminho else "",
        )
    arestas = [
        Connection(
            origin=resumos[edge.source],
            target=resumos[edge.target],
            kind=edge.kind.value,
            evidence=tuple(str(one) for one in edge.provenance.evidence),
            source=edge.provenance.source.value,
            confidence=edge.provenance.confidence.value,
            ingested_at=edge.validity.ingested_at,
        )
        for edge in next(iter(written.values())).edges
    ]
    return list(resumos.values()), arestas


def test_acha_o_no_pelo_nome(backend):
    found = backend.reader.find("/api/v1/itens", 10)

    assert ENDPOINT.key in [one.key for one in found]


def test_acha_o_modulo_pelo_caminho_e_traz_o_arquivo_como_fonte(backend):
    found = [one for one in backend.reader.find(MODULO, 10) if one.ref == MODULE]

    assert found, "o modulo tem de ser encontravel pelo caminho"
    assert found[0].source == f"{API.name}/{MODULO}"


def test_respeita_o_limite_e_o_texto_vazio(backend):
    assert len(backend.reader.find("contract", 1)) <= 1
    assert backend.reader.find("", 10) == []
    assert backend.reader.find("contract", 0) == []


def test_texto_que_nao_casa_com_nada_devolve_lista_vazia(backend):
    assert backend.reader.find("paralelepipedo", 10) == []


def test_no_que_existe_e_devolvido_e_o_que_nao_existe_e_none(backend):
    assert backend.reader.node(ENDPOINT) is not None
    assert backend.reader.node(NodeRef(NodeKind.ENDPOINT, "contract-api:GET /nao-existe")) is None


def test_arestas_que_chegam_no_endpoint_trazem_a_evidencia(backend):
    chegando = backend.reader.edges(ENDPOINT, Direction.IN)

    expoe = [edge for edge in chegando if edge.kind == "EXPOSES"]
    assert len(expoe) == 1
    assert expoe[0].origin.ref == MODULE, "EXPOSES vai do modulo para o endpoint"
    assert expoe[0].target.ref == ENDPOINT
    assert any("app/api/itens.py:14" in one for one in expoe[0].evidence)


def test_direcao_de_saida_nao_traz_as_de_entrada(backend):
    saindo = backend.reader.edges(ENDPOINT, Direction.OUT)

    assert "EXPOSES" not in [edge.kind for edge in saindo]


def test_direcao_ambos_traz_os_dois_lados(backend):
    chegando = backend.reader.edges(MODULE, Direction.IN)
    saindo = backend.reader.edges(MODULE, Direction.OUT)
    ambos = backend.reader.edges(MODULE, Direction.BOTH)

    assert len(ambos) == len(chegando) + len(saindo)
    assert {edge.kind for edge in saindo} >= {"EXPOSES", "PART_OF"}


def test_no_sem_vizinho_nenhum_devolve_lista_vazia(backend):
    sozinho = NodeRef(NodeKind.ENDPOINT, "contract-api:GET /nao-existe")

    assert backend.reader.edges(sozinho, Direction.BOTH) == []


def test_caminho_entre_dois_nos_traz_cada_passo_com_evidencia(backend):
    passos = backend.reader.path(ENDPOINT, DATASTORE, 6)

    assert passos, "endpoint e banco do mesmo repo se conectam"
    assert all(passo.evidence for passo in passos)
    assert passos[-1].target.ref == DATASTORE


def test_caminho_para_o_proprio_no_e_vazio(backend):
    assert backend.reader.path(ENDPOINT, ENDPOINT, 6) == []


def test_caminho_que_nao_cabe_na_profundidade_nao_e_inventado(backend):
    assert backend.reader.path(ENDPOINT, DATASTORE, 1) == []


def test_retrato_do_projeto_conta_a_estrutura(backend):
    overview = backend.reader.overview(PROJECT.slug)

    assert overview is not None
    assert [one.ref for one in overview.repos] == [REPO_REF]
    assert overview.endpoints == 1
    assert [one.ref for one in overview.datastores] == [DATASTORE]
    assert not overview.has_summary, "sem os resumos da Fase 2 o retrato e so estrutura"


def test_projeto_que_nao_existe_devolve_none(backend):
    assert backend.reader.overview("contract-nao-existe") is None
