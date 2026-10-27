from datetime import UTC, datetime, timedelta

import pytest

from engrama.domain.errors import (
    InvalidEvidence,
    InvalidNode,
    InvalidProvenance,
    InvalidRoute,
    InvalidValidity,
)
from engrama.domain.value_objects import (
    Confidence,
    Evidence,
    HttpMethod,
    HttpRoute,
    NodeKind,
    NodeRef,
    Provenance,
    Source,
    Validity,
)

COMMIT = "1141d440d8d66f0554f5c9e4d2329560f5591b09"
T0 = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


class TestEvidence:
    def test_no_codigo_cita_repo_arquivo_linha_e_commit_curto(self):
        evidence = Evidence.in_code(
            "phishing-quest-api", "adapter/http/router/ranking_router.go", COMMIT, 11
        )

        assert (
            str(evidence) == "phishing-quest-api/adapter/http/router/ranking_router.go:11@1141d44"
        )

    def test_em_documento_cita_o_link(self):
        assert str(Evidence.in_document("https://example.org/doc")) == "https://example.org/doc"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {},
            {"repo": "r", "path": "a.go"},
            {"repo": "r", "commit": COMMIT},
            {"repo": "r", "path": "a.go", "commit": COMMIT, "line": 0},
        ],
    )
    def test_rejeita_evidencia_incompleta(self, kwargs):
        with pytest.raises(InvalidEvidence):
            Evidence(**kwargs)


class TestProvenance:
    EVIDENCE = Evidence.in_code("r", "a.go", COMMIT, 1)

    def test_extracao_tem_confianca_alta(self):
        assert Provenance.extracted(self.EVIDENCE).confidence is Confidence.HIGH

    def test_extracao_sem_evidencia_e_invalida(self):
        with pytest.raises(InvalidProvenance):
            Provenance.extracted()

    def test_extracao_nao_aceita_confianca_menor(self):
        with pytest.raises(InvalidProvenance):
            Provenance(Source.EXTRACTION, Confidence.MEDIUM, (self.EVIDENCE,))

    def test_llm_nunca_tem_confianca_alta(self):
        with pytest.raises(InvalidProvenance):
            Provenance.inferred(self.EVIDENCE, confidence=Confidence.HIGH)

    def test_pessoa_pode_afirmar_sem_evidencia_externa(self):
        assert Provenance.stated_by_person().evidence == ()


class TestValidity:
    def test_vale_dentro_do_intervalo(self):
        validity = Validity.starting(T0).closed_at(T0 + timedelta(days=1))

        assert validity.holds_at(T0)
        assert not validity.holds_at(T0 + timedelta(days=1))
        assert not validity.holds_at(T0 - timedelta(seconds=1))

    def test_encerrar_devolve_copia_e_preserva_o_original(self):
        original = Validity.starting(T0)

        closed = original.closed_at(T0 + timedelta(hours=1))

        assert original.is_open
        assert closed.valid_to == T0 + timedelta(hours=1)

    def test_nao_encerra_duas_vezes(self):
        with pytest.raises(InvalidValidity):
            Validity.starting(T0).closed_at(T0).closed_at(T0)

    def test_exige_fuso_horario(self):
        with pytest.raises(InvalidValidity):
            Validity.starting(datetime(2026, 10, 27))

    def test_fim_antes_do_inicio_e_invalido(self):
        with pytest.raises(InvalidValidity):
            Validity(valid_from=T0, ingested_at=T0, valid_to=T0 - timedelta(days=1))


class TestHttpRoute:
    def test_forma_ignora_nome_do_parametro(self):
        a = HttpRoute(HttpMethod.GET, "/api/v1/items/{id}")
        b = HttpRoute(HttpMethod.GET, "/api/v1/items/{item_id}")

        assert a != b
        assert a.shape == b.shape == "GET /api/v1/items/{}"

    def test_raiz_e_valida(self):
        assert str(HttpRoute(HttpMethod.GET, "/")) == "GET /"

    @pytest.mark.parametrize(
        "path",
        ["api/v1/items", "/api/v1/items/", "/api/v1/items/:id", "/api/v1/items?x=1", "/a//b"],
    )
    def test_rejeita_caminho_fora_da_forma_canonica(self, path):
        with pytest.raises(InvalidRoute):
            HttpRoute(HttpMethod.GET, path)


def test_node_ref_rejeita_chave_vazia():
    with pytest.raises(InvalidNode):
        NodeRef(NodeKind.REPO, "  ")
