from datetime import UTC, datetime

import pytest

from engrama.domain.entities import Chunk, EdgeKind, Endpoint, Repo, Stack
from engrama.domain.errors import InvalidNode
from engrama.domain.services import (
    DocumentationGraphBuilder,
    DocumentChunker,
    MentionMatch,
    MentionReport,
)
from engrama.domain.value_objects import (
    Evidence,
    HttpMethod,
    HttpRoute,
    NodeKind,
    Source,
    Validity,
)
from engrama.domain.value_objects.document_facts import DocumentFile, DocumentKind, RouteMention

C = "d" * 40
API = Repo("forge-api", "forge", "https://github.com/x/forge-api", C, Stack.PYTHON_FASTAPI)
VALIDITY = Validity.starting(datetime(2026, 10, 1, tzinfo=UTC))
NO_MENTIONS = MentionReport((), (), ())


def document(path="README.md", kind=DocumentKind.DOC, text="# Forge\n\nFerramenta.", **kwargs):
    return DocumentFile(
        repo=API.name,
        path=path,
        kind=kind,
        title=kwargs.pop("title", "Forge"),
        text=text,
        evidence=Evidence.in_code(API.name, path, C),
        **kwargs,
    )


def build(documents=None, mentions=NO_MENTIONS, max_chars=1000):
    builder = DocumentationGraphBuilder(DocumentChunker(max_chars=max_chars))
    return builder.repository(API, documents or [document()], mentions, VALIDITY)


def edges_of(graph, kind):
    return [edge for edge in graph.edges if edge.kind is kind]


def test_documento_vira_no_e_pertence_ao_repo():
    graph = build()

    doc = next(n for n in graph.nodes if n.node_kind is NodeKind.DOC)
    assert doc.key == "forge-api:README.md"
    assert doc.title == "Forge"
    part_of = [e for e in edges_of(graph, EdgeKind.PART_OF) if e.source == doc.ref]
    assert [e.target for e in part_of] == [API.ref]


def test_adr_vira_decision_com_status():
    graph = build(
        [
            document(
                path="docs/decisoes/0001-path.md",
                kind=DocumentKind.DECISION,
                title="ADR 0001",
                status="aceita",
            )
        ]
    )

    decision = next(n for n in graph.nodes if n.node_kind is NodeKind.DECISION)
    assert (decision.key, decision.status) == ("forge-api:docs/decisoes/0001-path.md", "aceita")


def test_cada_chunk_pertence_ao_documento_com_a_linha_na_evidencia():
    text = "# Forge\n\nprosa.\n\n## Rotas\n\noutra prosa."
    graph = build([document(text=text)], max_chars=30)

    chunks = [n for n in graph.nodes if isinstance(n, Chunk)]
    assert [c.key for c in chunks] == ["forge-api:README.md#0", "forge-api:README.md#1"]
    chunk_edges = [e for e in edges_of(graph, EdgeKind.PART_OF) if e.source.kind is NodeKind.CHUNK]
    assert [e.target.key for e in chunk_edges] == ["forge-api:README.md"] * 2
    assert [e.provenance.evidence[0].line for e in chunk_edges] == [1, 5]


def test_readme_da_raiz_documenta_o_repo():
    graph = build()

    documented = edges_of(graph, EdgeKind.DOCUMENTED_IN)
    assert [(e.source, e.target.key) for e in documented] == [(API.ref, "forge-api:README.md")]
    assert documented[0].provenance.source is Source.EXTRACTION


def test_documento_que_nao_e_readme_da_raiz_nao_documenta_o_repo():
    graph = build([document(path="docs/architecture.md", title="Arquitetura")])

    assert edges_of(graph, EdgeKind.DOCUMENTED_IN) == []


def test_rota_citada_no_texto_documenta_o_endpoint():
    path = "docs/integracao_api.md"
    doc = document(path=path, text="# Integracao\n\nUse POST /api/v1/generate.", title="Integracao")
    endpoint = Endpoint(API.name, HttpRoute(HttpMethod.POST, "/api/v1/generate"))
    mention = RouteMention(API.name, path, endpoint.route, Evidence.in_code(API.name, path, C, 3))

    graph = build([doc], MentionReport((MentionMatch(mention, endpoint),), (), ()))

    documented = edges_of(graph, EdgeKind.DOCUMENTED_IN)
    assert [(e.source.key, e.target.key) for e in documented] == [
        (f"{API.name}:POST /api/v1/generate", f"{API.name}:{path}")
    ]
    assert [ev.line for ev in documented[0].provenance.evidence] == [3]


def test_citacoes_repetidas_da_mesma_rota_viram_uma_aresta_com_as_duas_evidencias():
    path = "docs/integracao_api.md"
    text = "# I\n\nPOST /api/v1/generate\n\ne de novo POST /api/v1/generate"
    doc = document(path=path, text=text)
    endpoint = Endpoint(API.name, HttpRoute(HttpMethod.POST, "/api/v1/generate"))
    matches = tuple(
        MentionMatch(
            RouteMention(API.name, path, endpoint.route, Evidence.in_code(API.name, path, C, line)),
            endpoint,
        )
        for line in (3, 5)
    )

    graph = build([doc], MentionReport(matches, (), ()))

    documented = edges_of(graph, EdgeKind.DOCUMENTED_IN)
    assert len(documented) == 1
    assert [ev.line for ev in documented[0].provenance.evidence] == [3, 5]


def test_o_no_do_endpoint_nao_entra_no_grafo_da_documentacao():
    """O endpoint ja existe no grafo, gravado pela camada de estrutura com o
    handler. Regravar aqui, sem handler, apagaria o que a estrutura sabe."""
    path = "docs/integracao_api.md"
    endpoint = Endpoint(API.name, HttpRoute(HttpMethod.POST, "/api/v1/generate"), handler="gera")
    mention = RouteMention(API.name, path, endpoint.route, Evidence.in_code(API.name, path, C, 3))

    graph = build(
        [document(path=path, text="# I\n\nPOST /api/v1/generate")],
        MentionReport((MentionMatch(mention, endpoint),), (), ()),
    )

    assert [n for n in graph.nodes if n.node_kind is NodeKind.ENDPOINT] == []


def test_documento_vazio_vira_no_sem_chunk():
    graph = build([document(path="docs/vazio.md", text="", title="vazio")])

    assert [n for n in graph.nodes if isinstance(n, Chunk)] == []
    assert any(n.node_kind is NodeKind.DOC for n in graph.nodes)


def test_chunk_recusa_faixa_de_linhas_impossivel():
    with pytest.raises(InvalidNode):
        Chunk("r", "a.md", 0, "texto", first_line=5, last_line=4)
    with pytest.raises(InvalidNode):
        Chunk("r", "a.md", 0, "texto", first_line=0, last_line=1)


def test_chunk_recusa_texto_em_branco_e_indice_negativo():
    with pytest.raises(InvalidNode):
        Chunk("r", "a.md", 0, "   \n ", first_line=1, last_line=2)
    with pytest.raises(InvalidNode):
        Chunk("r", "a.md", -1, "texto", first_line=1, last_line=1)


def test_chunk_cita_a_fonte_no_formato_das_perguntas_de_ouro():
    chunk = Chunk("forge-api", "README.md", 2, "texto", first_line=52, last_line=60)

    assert chunk.source == "forge-api/README.md:52"
