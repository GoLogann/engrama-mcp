"""O motor que o indice do Neo4j relata, quando a rodada degrada no meio.

Driver e embedder de mentira: o que se testa e so a contabilidade de qual
busca usou o que. As consultas de verdade estao em `tests/contracts/`.
"""

from engrama.application.ports.knowledge import (
    BY_MIXED,
    BY_VECTOR,
    BY_WORD,
    Embedder,
    EmbeddingUnavailable,
)
from engrama.infrastructure.neo4j.knowledge_index import Neo4jKnowledgeIndex


class StubDriver:
    def execute_query(self, *_args, **_kwargs):
        return [], None, None


class StubEmbedder(Embedder):
    """Responde `falhas` vezes e depois levanta, para simular o teto de taxa
    esgotando no meio da rodada."""

    def __init__(self, falha_a_partir_de: int | None = None) -> None:
        self.chamadas = 0
        self._falha_a_partir_de = falha_a_partir_de

    @property
    def dimensions(self) -> int:
        return 4

    def embed_documents(self, texts):
        return [(0.0, 0.0, 0.0, 1.0) for _ in texts]

    def embed_query(self, text: str):
        self.chamadas += 1
        if self._falha_a_partir_de is not None and self.chamadas >= self._falha_a_partir_de:
            raise EmbeddingUnavailable("teto de taxa")
        return (0.0, 0.0, 0.0, 1.0)


def index(embedder=None):
    return Neo4jKnowledgeIndex(StubDriver(), embedder)


def test_sem_embedder_o_motor_e_a_palavra():
    assert index().ranking() == BY_WORD


def test_com_embedder_o_motor_e_o_vetor():
    busca = index(StubEmbedder())

    busca.search("migrations", 5)

    assert busca.ranking() == BY_VECTOR


def test_rodada_que_degrada_no_meio_e_relatada_como_mista():
    """Chamar de `palavra` jogaria fora o que as primeiras buscas acharam por
    vetor; chamar de `vetor` esconderia a degradacao."""
    busca = index(StubEmbedder(falha_a_partir_de=3))

    for pergunta in ("uma", "duas", "tres", "quatro"):
        busca.search(pergunta, 5)

    assert busca.ranking() == BY_MIXED


def test_rodada_que_degrada_na_primeira_busca_e_so_palavra():
    busca = index(StubEmbedder(falha_a_partir_de=1))

    busca.search("uma", 5)

    assert busca.ranking() == BY_WORD


def test_antes_de_qualquer_busca_o_motor_previsto_e_o_vetor():
    assert index(StubEmbedder()).ranking() == BY_VECTOR


def test_consulta_vazia_nao_conta_motor_nenhum():
    busca = index(StubEmbedder())

    assert busca.search("", 5) == []
    assert busca.ranking() == BY_VECTOR, "nada foi medido ainda"
