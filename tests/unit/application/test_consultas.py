"""Os casos de uso das tools de leitura.

O que estas suites protegem e a honestidade da resposta: texto ambiguo nao
vira escolha, no inexistente nao vira resposta vazia que parece resposta, e
caminho que nao existe e dito como tal. Resposta errada com fonte convincente
e o pior defeito possivel num cerebro de conhecimento.
"""

from datetime import UTC, datetime

from engrama.application.dto.consulta import Connection, NodeSummary
from engrama.application.use_cases.explain_connection import ExplainConnection
from engrama.application.use_cases.find_usages import AnalyzeImpact, FindUsages
from engrama.application.use_cases.get_project_overview import FindNode, GetProjectOverview
from engrama.application.use_cases.resolve_node import ResolveNode
from engrama.domain.value_objects import NodeKind, NodeRef
from tests.fakes.reader import InMemoryReader

T0 = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)


def node(kind: NodeKind, key: str, label: str, repo: str = "", source: str = "") -> NodeSummary:
    return NodeSummary(ref=NodeRef(kind, key), label=label, repo=repo, source=source)


PROJETO = node(NodeKind.PROJECT, "forge", "Forge")
API = node(NodeKind.REPO, "forge-api", "forge-api", repo="forge-api")
FRONT = node(NodeKind.REPO, "forge-front", "forge-front", repo="forge-front")
MODULO = node(NodeKind.MODULE, "forge-front:src/services", "src/services", repo="forge-front")
ROTA = node(
    NodeKind.ENDPOINT,
    "forge-api:GET /api/v1/items",
    "GET /api/v1/items",
    repo="forge-api",
    source="forge-api/app/api/items.py:14",
)
OUTRA = node(
    NodeKind.ENDPOINT,
    "forge-api:POST /api/v1/items",
    "POST /api/v1/items",
    repo="forge-api",
)
MODULO_API = node(NodeKind.MODULE, "forge-api:app/api", "app/api", repo="forge-api")
BANCO = node(NodeKind.DATASTORE, "forge-api:postgres:forge", "postgres forge", repo="forge-api")

CHAMA = Connection(
    origin=MODULO,
    target=ROTA,
    kind="CALLS",
    evidence=("forge-front/src/services/api.ts:22", "forge-api/app/api/items.py:14"),
    source="extraction",
    confidence="high",
    ingested_at=T0,
)
EXPOE = Connection(
    origin=MODULO_API,
    target=ROTA,
    kind="EXPOSES",
    evidence=("forge-api/app/api/items.py:14",),
)
PERTENCE = Connection(
    origin=MODULO_API, target=API, kind="PART_OF", evidence=("forge-api/app/api:1",)
)
GUARDA = Connection(origin=API, target=BANCO, kind="STORES_IN", evidence=("forge-api/compose:9",))

# A cadeia completa, como o grafo real a tem: o front chama a rota, a rota e
# exposta por um modulo da API, o modulo pertence ao repo e o repo guarda no
# banco. E o caminho que `how_it_connects` precisa atravessar.
TODAS = [CHAMA, EXPOE, PERTENCE, GUARDA]


def reader(*extra_nodes, edges=None):
    nodes = [PROJETO, API, FRONT, MODULO, MODULO_API, ROTA, OUTRA, BANCO, *extra_nodes]
    return InMemoryReader(nodes=nodes, edges=edges if edges is not None else TODAS)


def resolver(graph=None):
    return ResolveNode(graph or reader())


# --------------------------------------------------------------- ResolveNode


def test_texto_exato_resolve_para_o_no():
    resolution = resolver().execute("GET /api/v1/items")

    assert resolution.found
    assert resolution.node == ROTA


def test_texto_que_casa_com_varios_nao_escolhe_nenhum():
    """`/api/v1/items` casa com GET e POST. Escolher seria adivinhar."""
    resolution = resolver().execute("/api/v1/items")

    assert not resolution.found
    assert resolution.ambiguous
    assert {one.key for one in resolution.candidates} == {ROTA.key, OUTRA.key}


def test_texto_que_casa_com_um_so_resolve_mesmo_sem_ser_exato():
    resolution = resolver().execute("postgres")

    assert resolution.node == BANCO


def test_texto_que_nao_casa_com_nada_e_dito_como_ausente():
    resolution = resolver().execute("paralelepipedo")

    assert resolution.missing
    assert not resolution.ambiguous
    assert resolution.candidates == ()


def test_texto_vazio_nao_consulta_o_grafo():
    graph = reader()

    resolution = ResolveNode(graph).execute("   ")

    assert resolution.missing
    assert resolution.query == ""


# ----------------------------------------------------------------- FindUsages


def test_who_uses_traz_quem_chama_a_rota_com_evidencia_dos_dois_lados():
    """Vem tambem o modulo que expoe a rota, e esta certo assim.

    Toda aresta que chega carrega o proprio `kind`, entao a resposta se
    descreve: `CALLS` e uso e `EXPOSES` e onde a rota mora. Filtrar aqui
    esconderia de quem pergunta onde o endpoint esta definido, que e a
    primeira coisa que se quer depois de saber quem o chama.
    """
    graph = reader()

    resolution, report = FindUsages(graph, ResolveNode(graph)).execute("GET /api/v1/items")

    assert resolution.found
    assert report is not None
    chamadas = [edge for edge in report.incoming if edge.kind == "CALLS"]
    assert [edge.origin.key for edge in chamadas] == [MODULO.key]
    assert chamadas[0].evidence == CHAMA.evidence
    assert {edge.kind for edge in report.incoming} == {"CALLS", "EXPOSES"}
    assert report.outgoing == (), "who_uses olha so quem chega"


def test_who_uses_de_texto_ambiguo_nao_inventa_relatorio():
    graph = reader()

    resolution, report = FindUsages(graph, ResolveNode(graph)).execute("/api/v1/items")

    assert report is None
    assert resolution.ambiguous


def test_who_uses_aponta_os_repos_de_fora():
    graph = reader()

    _resolution, report = FindUsages(graph, ResolveNode(graph)).execute("GET /api/v1/items")

    assert report.repos_affected == ("forge-front",)


# --------------------------------------------------------------- AnalyzeImpact


def test_impacto_olha_os_dois_lados():
    graph = reader()

    _resolution, report = AnalyzeImpact(graph, ResolveNode(graph)).execute("forge-api")

    assert [edge.target.key for edge in report.outgoing] == [BANCO.key]
    assert report.total == len(report.incoming) + len(report.outgoing)


def test_impacto_de_no_sem_vizinho_e_zero_e_nao_erro():
    graph = reader(edges=[])

    _resolution, report = AnalyzeImpact(graph, ResolveNode(graph)).execute("GET /api/v1/items")

    assert report.total == 0
    assert report.repos_affected == ()


# ----------------------------------------------------------- ExplainConnection


def test_caminho_entre_dois_nos_traz_a_evidencia_de_cada_aresta():
    graph = reader()

    _origin, _target, path = ExplainConnection(graph, ResolveNode(graph)).execute(
        "src/services", "postgres"
    )

    assert path.found
    assert [step.kind for step in path.steps] == ["CALLS", "EXPOSES", "PART_OF", "STORES_IN"]
    assert all(step.evidence for step in path.steps), "aresta sem evidencia nao se explica"


def test_sem_caminho_a_resposta_e_que_nao_ha_caminho():
    graph = reader(edges=[GUARDA])

    _origin, _target, path = ExplainConnection(graph, ResolveNode(graph)).execute(
        "src/services", "postgres"
    )

    assert path is not None
    assert not path.found
    assert path.length == 0


def test_caminho_respeita_a_profundidade_pedida():
    graph = reader()

    _origin, _target, path = ExplainConnection(graph, ResolveNode(graph)).execute(
        "src/services", "postgres", max_depth=1
    )

    assert not path.found


def test_caminho_com_ponta_ambigua_nao_e_calculado():
    graph = reader()

    origin, _target, path = ExplainConnection(graph, ResolveNode(graph)).execute(
        "/api/v1/items", "postgres"
    )

    assert path is None
    assert origin.ambiguous


# -------------------------------------------------- GetProjectOverview e Find


def test_retrato_conta_a_estrutura_extraida():
    overview = GetProjectOverview(reader()).execute("forge")

    assert overview.project == "forge"
    assert {one.key for one in overview.repos} == {API.key, FRONT.key}
    assert overview.endpoints == 2
    assert overview.modules == 2


def test_retrato_diz_que_ainda_nao_tem_resumo():
    """Sem os resumos da Fase 2 o retrato e so estrutura, e quem apresenta
    precisa saber disso para nao vender um retrato completo."""
    overview = GetProjectOverview(reader()).execute("forge")

    assert not overview.has_summary


def test_projeto_que_nao_existe_devolve_nada():
    assert GetProjectOverview(reader()).execute("inexistente") is None
    assert GetProjectOverview(reader()).execute("  ") is None


def test_find_devolve_as_opcoes_em_vez_de_escolher():
    found = FindNode(reader()).execute("/api/v1/items")

    assert {one.key for one in found} == {ROTA.key, OUTRA.key}


def test_find_respeita_o_limite_e_o_texto_vazio():
    assert len(FindNode(reader()).execute("/api/v1/items", limit=1)) == 1
    assert FindNode(reader()).execute("") == []
    assert FindNode(reader()).execute("items", limit=0) == []
