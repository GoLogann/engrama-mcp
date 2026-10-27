from datetime import UTC, datetime

import pytest

from engrama.domain.entities import Edge, EdgeKind
from engrama.domain.errors import InvalidEdge
from engrama.domain.value_objects import Evidence, NodeKind, NodeRef, Provenance, Validity

COMMIT = "43ed8ffd82eec304af1cff34f60ff523dc4edfa2"
VALIDITY = Validity.starting(datetime(2026, 9, 17, tzinfo=UTC))
CALL_SITE = Evidence.in_code(
    "phishing_quest", "lib/app/data/repositories/game/game_repository.dart", COMMIT, 21
)

APP_MODULE = NodeRef(NodeKind.MODULE, "phishing_quest:lib/app/data/repositories/game")
ANSWER_ENDPOINT = NodeRef(NodeKind.ENDPOINT, "phishing-quest-api:POST /api/v1/game/answer")
CONCEPT = NodeRef(NodeKind.CONCEPT, "pista")


def test_chamada_extraida_do_codigo_e_valida():
    edge = Edge(
        EdgeKind.CALLS, APP_MODULE, ANSWER_ENDPOINT, Provenance.extracted(CALL_SITE), VALIDITY
    )

    assert str(edge) == (
        "Module(phishing_quest:lib/app/data/repositories/game) -[CALLS]-> "
        "Endpoint(phishing-quest-api:POST /api/v1/game/answer)"
    )


def test_llm_nao_cria_aresta_estrutural():
    with pytest.raises(InvalidEdge, match="nao pode vir de llm"):
        Edge(EdgeKind.CALLS, APP_MODULE, ANSWER_ENDPOINT, Provenance.inferred(CALL_SITE), VALIDITY)


def test_llm_pode_ligar_conceito():
    edge = Edge(
        EdgeKind.MENTIONS_CONCEPT, APP_MODULE, CONCEPT, Provenance.inferred(CALL_SITE), VALIDITY
    )

    assert edge.provenance.source == "llm"


def test_rejeita_par_de_familias_que_a_aresta_nao_liga():
    with pytest.raises(InvalidEdge, match="nao liga"):
        Edge(EdgeKind.CALLS, ANSWER_ENDPOINT, APP_MODULE, Provenance.extracted(CALL_SITE), VALIDITY)


def test_rejeita_laco():
    module = NodeRef(NodeKind.MODULE, "r:a")
    with pytest.raises(InvalidEdge, match="ele mesmo"):
        Edge(EdgeKind.PART_OF, module, module, Provenance.extracted(CALL_SITE), VALIDITY)


def test_toda_aresta_tem_regra():
    from engrama.domain.entities.edge import RULES

    assert set(RULES) == set(EdgeKind)


class TestArestaSemEvidencia:
    """Principio 3 do plano: toda aresta carrega evidencia. A unica excecao e a
    aresta que parte de um Episodio, porque o proprio episodio (autor e data) e a prova."""

    PESSOA = Provenance.stated_by_person()
    ISSUE = NodeRef(NodeKind.ISSUE, "r#1")
    EPISODIO = NodeRef(NodeKind.EPISODE, "ep-1")
    PESSOA_NO = NodeRef(NodeKind.PERSON, "GoLogann")

    def test_aresta_de_modulo_afirmada_por_pessoa_sem_evidencia_e_recusada(self):
        with pytest.raises(InvalidEdge, match="sem evidencia"):
            Edge(EdgeKind.REFERENCES_ISSUE, APP_MODULE, self.ISSUE, self.PESSOA, VALIDITY)

    def test_mencao_de_conceito_por_pessoa_sem_evidencia_e_recusada(self):
        with pytest.raises(InvalidEdge, match="sem evidencia"):
            Edge(EdgeKind.MENTIONS_CONCEPT, APP_MODULE, CONCEPT, self.PESSOA, VALIDITY)

    def test_aresta_que_parte_de_episodio_dispensa_evidencia(self):
        about = Edge(EdgeKind.ABOUT, self.EPISODIO, APP_MODULE, self.PESSOA, VALIDITY)
        author = Edge(EdgeKind.AUTHORED_BY, self.EPISODIO, self.PESSOA_NO, self.PESSOA, VALIDITY)

        assert about.provenance.evidence == author.provenance.evidence == ()

    @pytest.mark.parametrize("provenance", [None, "extracao"])
    def test_proveniencia_precisa_ser_uma_proveniencia(self, provenance):
        with pytest.raises(InvalidEdge):
            Edge(EdgeKind.CALLS, APP_MODULE, ANSWER_ENDPOINT, provenance, VALIDITY)

    @pytest.mark.parametrize("validity", [None, "2026-09-17"])
    def test_validade_precisa_ser_uma_validade(self, validity):
        with pytest.raises(InvalidEdge):
            Edge(
                EdgeKind.CALLS,
                APP_MODULE,
                ANSWER_ENDPOINT,
                Provenance.extracted(CALL_SITE),
                validity,
            )
