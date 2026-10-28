from engrama.application.dto.ingestion import Catalog, RepositorySpec
from engrama.application.use_cases.index_documents import IndexDocuments, documentation_owner
from engrama.application.use_cases.read_repository_documents import ReadRepositoryDocuments
from engrama.domain.entities import EdgeKind, Endpoint, Project, Repo, Stack
from engrama.domain.services import (
    DocumentationGraphBuilder,
    DocumentChunker,
    RouteMentionMatcher,
    RouteNormalizer,
    StructuralGraphBuilder,
)
from engrama.domain.value_objects import (
    Evidence,
    HttpMethod,
    HttpRoute,
    NodeKind,
    Validity,
)
from engrama.domain.value_objects.code_facts import DeclaredRoute
from engrama.infrastructure.documents import RepositoryDocumentExtractor
from engrama.infrastructure.security.secret_scanner import RegexSecretScanner
from tests.fakes.graph import InMemoryGraph
from tests.fakes.sources import FixedClock, InMemorySourceRepository, StaticCatalog

C = "b" * 40
PROJECT = Project("forge", "Forge")
API = Repo("forge-api", "forge", "https://github.com/x/forge-api", C, Stack.PYTHON_FASTAPI)
FRONT = Repo("forge-front", "forge", "https://github.com/x/forge-front", C, Stack.TYPESCRIPT_REACT)
CATALOG = Catalog((PROJECT,), (RepositorySpec(API), RepositorySpec(FRONT, consumes=("forge-api",))))
FILES = {
    "forge-api": {
        "README.md": "# Forge API\n\nGera exemplos.\n",
        "docs/api.md": "# Integracao\n\nUse POST /api/v1/generate para gerar.\n",
        "docs/decisoes/0001-rota.md": "# ADR 0001\n\n- **Status:** aceita\n",
        "migrate/flyway.config": "flyway.password=naovaiparaografo\nflyway.user=app\n",
    },
    "forge-front": {"README.md": "# Forge Front\n\nSite em React.\n"},
}


def indexer(graph, files=None, endpoints=None):
    sources = InMemorySourceRepository(files if files is not None else FILES)
    read = ReadRepositoryDocuments(
        sources, RepositoryDocumentExtractor(RouteNormalizer()), RegexSecretScanner()
    )
    if endpoints is not None:
        _write_structure(graph, endpoints)
    return IndexDocuments(
        catalog=StaticCatalog(CATALOG),
        read=read,
        matcher=RouteMentionMatcher(),
        builder=DocumentationGraphBuilder(DocumentChunker(max_chars=1000)),
        writer=graph,
        structure=graph,
        clock=FixedClock(),
    )


def _write_structure(graph, routes):
    """A estrutura entra pelo caminho normal, para os endpoints virem do grafo."""
    builder = StructuralGraphBuilder()
    declared = [
        DeclaredRoute(
            API.name,
            "app",
            route,
            Evidence.in_code(API.name, "app/main.py", C, 10),
        )
        for route in routes
    ]
    validity = Validity.starting(FixedClock().now())
    graph.write(
        {API.name: builder.repository(PROJECT, API, ["app"], declared, [], [], validity)},
        run_id="estrutura",
        at=FixedClock().now(),
    )


def test_grava_documentos_pedacos_e_pertencimento():
    graph = InMemoryGraph()

    report = indexer(graph).execute()

    kinds = [node.node_kind for node in graph.nodes.values()]
    # forge-api: README, docs/api.md e flyway.config, mais o ADR; forge-front: README.
    assert kinds.count(NodeKind.DOC) == 4
    assert kinds.count(NodeKind.DECISION) == 1
    assert kinds.count(NodeKind.CHUNK) == 5
    assert [summary.repo for summary in report.repos] == ["forge-api", "forge-front"]
    assert report.repos[0].documents == 3
    assert report.repos[0].decisions == 1


def test_mascara_o_segredo_antes_de_o_texto_virar_no():
    graph = InMemoryGraph()

    report = indexer(graph).execute()

    texts = [node.text for node in graph.nodes.values() if node.node_kind is NodeKind.CHUNK]
    assert all("naovaiparaografo" not in text for text in texts)
    assert any("flyway.password=<redacted>" in text for text in texts)
    assert report.repos[0].redactions == 1


def test_rota_citada_liga_no_endpoint_que_existe_no_grafo():
    graph = InMemoryGraph()
    route = HttpRoute(HttpMethod.POST, "/api/v1/generate")

    report = indexer(graph, endpoints=[route]).execute()

    documented = [
        stored.edge
        for stored in graph.open_edges(EdgeKind.DOCUMENTED_IN)
        if stored.edge.source.kind is NodeKind.ENDPOINT
    ]
    assert [(e.source.key, e.target.key) for e in documented] == [
        (f"{API.name}:POST /api/v1/generate", f"{API.name}:docs/api.md")
    ]
    assert report.known_endpoints == 1
    assert report.repos[0].endpoints_documented == 1


def test_sem_estrutura_no_grafo_indexa_e_avisa():
    graph = InMemoryGraph()

    report = indexer(graph).execute()

    assert report.known_endpoints == 0
    assert [str(mention.route) for mention in report.unmatched] == ["POST /api/v1/generate"]
    assert any(node.node_kind is NodeKind.CHUNK for node in graph.nodes.values())


def test_a_documentacao_nao_aposenta_as_arestas_da_estrutura():
    """Donos diferentes por camada: indexar documentos duas vezes nao fecha o
    que a ingestao da estrutura gravou."""
    graph = InMemoryGraph()
    route = HttpRoute(HttpMethod.POST, "/api/v1/generate")
    index = indexer(graph, endpoints=[route])

    index.execute()
    index.execute()

    exposes = graph.open_edges(EdgeKind.EXPOSES)
    assert len(exposes) == 1, "a EXPOSES da estrutura continua aberta"
    assert {stored.owner for stored in graph.open_edges(EdgeKind.PART_OF)} == {
        API.name,
        documentation_owner(API.name),
        documentation_owner(FRONT.name),
    }


def test_documento_que_sumiu_do_repo_tem_a_aresta_fechada():
    graph = InMemoryGraph()
    index = indexer(graph)
    index.execute()

    files = {name: dict(tree) for name, tree in FILES.items()}
    del files["forge-api"]["docs/decisoes/0001-rota.md"]
    indexer(graph, files=files).execute()

    open_documents = {
        stored.edge.source.key
        for stored in graph.open_edges(EdgeKind.PART_OF)
        if stored.edge.source.kind in (NodeKind.DOC, NodeKind.DECISION)
    }
    assert f"{API.name}:docs/decisoes/0001-rota.md" not in open_documents
    assert f"{API.name}:README.md" in open_documents


def test_indexar_um_repo_so_nao_puxa_os_outros():
    graph = InMemoryGraph()

    report = indexer(graph).execute(only=["forge-front"])

    assert [summary.repo for summary in report.repos] == ["forge-front"]
    assert {stored.owner for stored in graph.open_edges(EdgeKind.PART_OF)} == {
        documentation_owner(FRONT.name)
    }


def test_endpoint_nao_e_regravado_pela_documentacao():
    graph = InMemoryGraph()
    route = HttpRoute(HttpMethod.POST, "/api/v1/generate")
    _write_structure(graph, [route])
    before = graph.nodes[(NodeKind.ENDPOINT.value, f"{API.name}:POST /api/v1/generate")]
    assert isinstance(before, Endpoint)

    indexer(graph).execute()

    after = graph.nodes[(NodeKind.ENDPOINT.value, f"{API.name}:POST /api/v1/generate")]
    assert after is before
