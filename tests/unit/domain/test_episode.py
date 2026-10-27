from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from engrama.domain.entities import EdgeKind, Episode, EpisodeType
from engrama.domain.errors import EpisodeAlreadySuperseded, InvalidEpisode
from engrama.domain.value_objects import Evidence, NodeKind, NodeRef, Provenance, Source

T0 = datetime(2026, 10, 27, 15, 0, tzinfo=UTC)
LOGAN = NodeRef(NodeKind.PERSON, "GoLogann")
PIPELINE = NodeRef(NodeKind.MODULE, "phishforge-api:app/domain/services")


def recorded(**overrides) -> Episode:
    fields = {
        "id": "ep-1",
        "episode_type": EpisodeType.LEARNING,
        "text": "RAG melhorou a fidelidade das pistas geradas",
        "about": (PIPELINE,),
        "author": LOGAN,
        "at": T0,
    }
    return Episode.record(**(fields | overrides))


def test_episode_nunca_e_editado():
    with pytest.raises(FrozenInstanceError):
        recorded().text = "outro texto"


def test_substituir_encerra_o_antigo_e_liga_o_sucessor():
    later = T0 + timedelta(days=7)

    closed, successor = recorded().supersede(
        successor_id="ep-2", text="Com o modelo novo, RAG deixou de ajudar", author=LOGAN, at=later
    )

    assert closed.id == "ep-1"
    assert closed.validity.valid_to == later
    assert not closed.is_current
    assert successor.is_current
    assert successor.supersedes == "ep-1"
    assert successor.about == (PIPELINE,)
    assert successor.episode_type is EpisodeType.LEARNING


def test_episodio_encerrado_nao_e_substituido_de_novo():
    closed, _ = recorded().supersede(successor_id="ep-2", text="x", author=LOGAN, at=T0)

    with pytest.raises(EpisodeAlreadySuperseded):
        closed.supersede(successor_id="ep-3", text="y", author=LOGAN, at=T0)


def test_semente_de_documento_guarda_quando_passou_a_valer():
    doc = Evidence.in_document(
        "https://github.com/LABit-UFPA/phishforge-api/blob/815bd3a/docs/analise_rag_vs_no_rag.md"
    )
    seeded = recorded(
        valid_from=datetime(2026, 1, 16, tzinfo=UTC), provenance=Provenance.from_document(doc)
    )

    assert seeded.validity.valid_from.month == 1
    assert seeded.validity.ingested_at == T0
    assert all(edge.provenance.source is Source.DOCUMENT for edge in seeded.edges())


def test_arestas_do_episodio():
    _, successor = recorded().supersede(successor_id="ep-2", text="x", author=LOGAN, at=T0)

    kinds = [(edge.kind, edge.target) for edge in successor.edges()]

    assert kinds == [
        (EdgeKind.ABOUT, PIPELINE),
        (EdgeKind.AUTHORED_BY, LOGAN),
        (EdgeKind.SUPERSEDES, NodeRef(NodeKind.EPISODE, "ep-1")),
    ]


@pytest.mark.parametrize(
    "overrides",
    [
        {"text": "   "},
        {"about": ()},
        {"about": (NodeRef(NodeKind.EPISODE, "ep-0"),)},
        {"author": PIPELINE},
        {"supersedes": "ep-1"},
    ],
)
def test_rejeita_episodio_invalido(overrides):
    with pytest.raises(InvalidEpisode):
        recorded(**overrides)
