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
