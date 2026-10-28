"""Contrato de KnowledgeIndex.

A mesma suite roda contra o indice em memoria e contra o do Neo4j. As notas
dos dois nao sao iguais (so o Neo4j tem BM25, radical de palavra e embedding
de verdade), entao o contrato cobra o que os dois precisam garantir: ordem
decrescente de nota, limite respeitado, consulta vazia sem resultado, so
pedaco de documento que ainda vale, e dizer por qual motor ordenou.

Os dois lados usam o `FakeEmbedder` — tambem o backend do Neo4j, de proposito.
Medir a qualidade da Voyage e trabalho de `engrama check-sources`, com o corpus
de verdade; aqui o que se testa e a mecanica da busca, e ela precisa rodar no
CI sem chave de API nenhuma.

Os testes no Neo4j usam chaves com o prefixo `contract-` e as apagam no fim;
sem Neo4j acessivel, sao pulados.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

import pytest

from engrama.application.ports.graph import GraphWriter
from engrama.application.ports.knowledge import (
    BY_VECTOR,
    BY_WORD,
    Embedder,
    KnowledgeIndex,
    VectorStore,
)
from engrama.domain.entities import Chunk, Repo, Stack
from engrama.domain.services import DocumentationGraphBuilder, DocumentChunker, MentionReport
from engrama.domain.value_objects import Evidence, Validity
from engrama.domain.value_objects.document_facts import DocumentFile, DocumentKind
from tests.fakes.graph import InMemoryGraph
from tests.fakes.knowledge import FakeEmbedder, InMemoryKnowledgeIndex, InMemoryVectorStore

C = "f" * 40
T0 = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)
T1 = datetime(2026, 10, 29, 9, 0, tzinfo=UTC)
REPO = Repo("contract-docs", "contract-project", "https://x/contract-docs", C, Stack.GO_GIN)
OWNER = "contract-docs:docs"
VALIDITY = Validity.starting(T0)

README = DocumentFile(
    repo=REPO.name,
    path="README.md",
    kind=DocumentKind.DOC,
    title="Contrato",
    text="# Contrato\n\nO ranking usa pontuacao por tentativa.",
    evidence=Evidence.in_code(REPO.name, "README.md", C),
)
DECISION = DocumentFile(
    repo=REPO.name,
    path="docs/decisoes/0001-fuso.md",
    kind=DocumentKind.DECISION,
    title="ADR 0001",
    text="# ADR 0001\n\nO fuso horario das datas e sempre UTC.",
    evidence=Evidence.in_code(REPO.name, "docs/decisoes/0001-fuso.md", C),
    status="aceita",
)
EMPTY = replace(README, path="docs/vazio.md", title="vazio", text="")


def graphs(documents, at=T0):
    builder = DocumentationGraphBuilder(DocumentChunker(max_chars=1000))
    validity = Validity.starting(T0, ingested_at=at)
    return {OWNER: builder.repository(REPO, documents, MentionReport((), (), ()), validity)}


@dataclass(frozen=True)
class Backend:
    writer: GraphWriter
    index: KnowledgeIndex
    vectors: VectorStore
    # A mesma base, sem embedder: a reserva por palavra do ADR 0011.
    reserve: KnowledgeIndex = None  # type: ignore[assignment]
    embedder: Embedder = field(default_factory=FakeEmbedder)
    settle: Callable[[], None] = lambda: None

    def write(self, documents: Sequence[DocumentFile], run_id: str, at=T0) -> None:
        """Grava os documentos e os vetores dos pedacos, como `IndexDocuments`.

        Vetor depois da escrita, na mesma ordem do caso de uso: sem isso a
        metade vetorial da busca nao enxerga o que acabou de entrar.
        """
        graph = graphs(documents, at=at)
        self.writer.write(graph, run_id=run_id, at=at)
        chunks = [node for one in graph.values() for node in one.nodes if isinstance(node, Chunk)]
        self.vectors.store(
            dict(
                zip(
                    (chunk.key for chunk in chunks),
                    self.embedder.embed_documents([chunk.text for chunk in chunks]),
                    strict=True,
                )
            )
        )
        self.settle()


@pytest.fixture(params=["memory", pytest.param("neo4j", marks=pytest.mark.integration)])
def backend(request):
    if request.param == "memory":
        fake = InMemoryGraph()
        embedder = FakeEmbedder()
        yield Backend(
            writer=fake,
            index=InMemoryKnowledgeIndex(fake, embedder),
            vectors=InMemoryVectorStore(fake),
            reserve=InMemoryKnowledgeIndex(fake),
            embedder=embedder,
        )
        return

    from engrama.bootstrap.settings import Settings
    from engrama.infrastructure.neo4j.connection import open_driver
    from engrama.infrastructure.neo4j.graph_writer import Neo4jGraphWriter
    from engrama.infrastructure.neo4j.knowledge_index import Neo4jKnowledgeIndex
    from engrama.infrastructure.neo4j.vector_store import Neo4jVectorStore

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
    embedder = FakeEmbedder()

    # Os indices de texto completo e vetorial sao assincronos: sem esperar, a
    # busca logo depois da escrita pode nao ver o pedaco que acabou de entrar.
    def settle() -> None:
        driver.execute_query("CALL db.awaitIndexes(60)")

    settle()
    yield Backend(
        writer=writer,
        index=Neo4jKnowledgeIndex(driver, embedder),
        vectors=Neo4jVectorStore(driver),
        reserve=Neo4jKnowledgeIndex(driver),
        embedder=embedder,
        settle=settle,
    )
    driver.execute_query(cleanup)
    resource.close()


def hits(backend, query, limit=10):
    return [hit for hit in backend.index.search(query, limit) if hit.repo == REPO.name]


def ours(backend):
    return [document for document in backend.index.documents() if document.repo == REPO.name]


def test_acha_o_pedaco_pela_palavra_do_texto(backend):
    backend.write([README, DECISION], run_id="k1")

    found = hits(backend, "fuso horario")

    assert found, "a busca nao achou o pedaco que tem as palavras"
    assert found[0].path == DECISION.path
    assert found[0].document_kind == "Decision"
    assert found[0].source == f"{REPO.name}/{DECISION.path}:1"
    assert found[0].covers(1)


def test_ordena_por_nota_decrescente(backend):
    backend.write([README, DECISION], run_id="k1")

    found = hits(backend, "ranking pontuacao tentativa fuso horario UTC")

    assert len(found) == 2
    assert found[0].score >= found[1].score


def test_respeita_o_limite(backend):
    backend.write([README, DECISION], run_id="k1")

    assert len(hits(backend, "ranking fuso", limit=1)) <= 1
    assert backend.index.search("ranking fuso", limit=0) == []


def test_consulta_sem_palavra_nao_devolve_nada(backend):
    backend.write([README, DECISION], run_id="k1")

    assert backend.index.search("", limit=5) == []
    assert backend.index.search("   ?!  ", limit=5) == []


def test_palavra_que_nao_esta_em_documento_nenhum_ainda_traz_vizinhos(backend):
    """Consequencia da busca por significado, registrada de proposito (ADR 0011).

    Busca vetorial nao tem a nocao de "nao achei": ela devolve sempre os k
    mais proximos. Entao uma palavra que nao esta em documento nenhum deixa de
    voltar vazia — o que volta sao os vizinhos mais proximos no espaco. Quem
    decide se isso e relevante e quem consome, nao o indice.
    """
    backend.write([README, DECISION], run_id="k1")

    found = hits(backend, "paralelepipedo")

    assert found, "a busca vetorial sempre tem um vizinho mais proximo"


def test_documento_removido_do_repo_sai_da_busca(backend):
    backend.write([README, DECISION], run_id="k1")

    backend.write([README], run_id="k2", at=T1)

    # Nao vale mais exigir busca vazia: a metade vetorial devolve o vizinho
    # mais proximo de qualquer jeito. O que o contrato cobra e que o pedaco do
    # documento removido nao esteja entre os resultados.
    assert DECISION.path not in [hit.path for hit in hits(backend, "fuso horario")]
    assert [document.path for document in ours(backend)] == [README.path]


def test_lista_os_documentos_com_o_numero_de_pedacos(backend):
    backend.write([README, DECISION, EMPTY], run_id="k1")

    found = {document.path: document for document in ours(backend)}

    assert set(found) == {README.path, DECISION.path, EMPTY.path}
    assert found[README.path].chunks == 1
    assert found[README.path].kind == "Doc"
    assert found[DECISION.path].kind == "Decision"
    assert found[EMPTY.path].chunks == 0, "documento vazio existe e nao tem pedaco"


@pytest.mark.parametrize("query", ["NOT", "AND", "OR", "fuso OR horario", "fuso AND NOT x"])
def test_palavra_que_e_operador_de_busca_nao_quebra(backend, query):
    """`AND`, `OR` e `NOT` sao operadores do Lucene. Uma pergunta que traga uma
    dessas palavras nao pode derrubar a busca: na Fase 4 isso e erro de tool."""
    backend.write([README, DECISION], run_id="k1")

    backend.index.search(query, limit=5)


def test_hit_diz_quando_o_grafo_soube_do_pedaco(backend):
    backend.write([README, DECISION], run_id="k1")

    found = hits(backend, "fuso horario")

    assert found[0].ingested_at == T0


def test_diz_por_qual_motor_ordena(backend):
    assert backend.index.ranking() == BY_VECTOR
    assert backend.reserve.ranking() == BY_WORD


def test_a_reserva_por_palavra_responde_sem_embeddings(backend):
    """Sem chave de API a busca cai para palavra (ADR 0011). Ela acha menos,
    mas precisa achar: e o modo de quem so quer rodar o projeto."""
    backend.write([README, DECISION], run_id="k1")

    found = [hit for hit in backend.reserve.search("fuso horario", 10) if hit.repo == REPO.name]

    assert [hit.path for hit in found] == [DECISION.path]
