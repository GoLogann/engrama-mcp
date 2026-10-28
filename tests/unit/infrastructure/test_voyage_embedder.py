"""O adapter da Voyage, com cliente de mentira.

Teste nao bate na API: gastaria cota, exigiria chave no CI e falharia por
motivo que nao e do codigo. O que se testa aqui e o que o adapter decide —
`input_type` por caminho, divisao em lotes e recusa de vetor com tamanho
diferente do indice. A qualidade do modelo e medida por `engrama
check-sources`, com o corpus de verdade.
"""

import pytest

from engrama.infrastructure.embeddings import voyage_embedder
from engrama.infrastructure.embeddings.voyage_embedder import VoyageEmbedder


class StubResult:
    def __init__(self, embeddings: list[list[float]]) -> None:
        self.embeddings = embeddings


class StubClient:
    def __init__(self, dimensions: int = 1024, **_kwargs) -> None:
        self.dimensions = dimensions
        self.calls: list[tuple[list[str], str, str]] = []

    def embed(self, texts, model, input_type):
        self.calls.append((list(texts), model, input_type))
        return StubResult([[0.1] * self.dimensions for _ in texts])


@pytest.fixture
def stub(monkeypatch):
    client = StubClient()
    monkeypatch.setattr(voyage_embedder.voyageai, "Client", lambda **_kwargs: client)
    return client


def test_chave_vazia_e_recusada_na_construcao(monkeypatch):
    monkeypatch.setattr(voyage_embedder.voyageai, "Client", lambda **_kwargs: StubClient())

    with pytest.raises(ValueError, match="VOYAGE_API_KEY"):
        VoyageEmbedder(api_key="")


def test_documento_e_pergunta_usam_input_type_diferente(stub):
    embedder = VoyageEmbedder(api_key="al-x")

    embedder.embed_documents(["um texto"])
    embedder.embed_query("uma pergunta")

    assert [call[2] for call in stub.calls] == ["document", "query"]


def test_divide_em_lotes_por_quantidade(stub):
    embedder = VoyageEmbedder(api_key="al-x")

    vectors = embedder.embed_documents([f"texto {number}" for number in range(150)])

    assert len(vectors) == 150, "a ordem e a quantidade sobrevivem aos lotes"
    assert [len(call[0]) for call in stub.calls] == [64, 64, 22]


def test_divide_em_lotes_por_tamanho(stub):
    """Pelo tamanho, nao so pela quantidade: o teto por minuto da conta sem
    forma de pagamento e de tokens, e um lote de poucos textos longos passa
    dele com folga."""
    quase_cheio = "x" * (voyage_embedder._MAX_CHARS - 10)

    VoyageEmbedder(api_key="al-x").embed_documents([quase_cheio, quase_cheio, "z"])

    assert [len(call[0]) for call in stub.calls] == [1, 2]


def test_teto_de_taxa_espera_e_tenta_de_novo(stub, monkeypatch):
    esperas = []
    monkeypatch.setattr(voyage_embedder.time, "sleep", esperas.append)
    original = stub.embed
    chamadas = []

    def recusa_a_primeira(texts, model, input_type):
        chamadas.append(texts)
        if len(chamadas) == 1:
            raise voyage_embedder.voyageai.error.RateLimitError("3 RPM")
        return original(texts, model, input_type)

    monkeypatch.setattr(stub, "embed", recusa_a_primeira)

    vectors = VoyageEmbedder(api_key="al-x").embed_documents(["um texto"])

    assert len(vectors) == 1, "a segunda tentativa vale"
    assert esperas == [25.0], "esperou antes de tentar de novo"


def test_teto_de_taxa_que_nao_passa_deixa_o_erro_subir(stub, monkeypatch):
    monkeypatch.setattr(voyage_embedder.time, "sleep", lambda _seconds: None)

    def sempre_recusa(*_args, **_kwargs):
        raise voyage_embedder.voyageai.error.RateLimitError("3 RPM")

    monkeypatch.setattr(stub, "embed", sempre_recusa)

    with pytest.raises(voyage_embedder.voyageai.error.RateLimitError):
        VoyageEmbedder(api_key="al-x").embed_documents(["um texto"])


def test_lista_vazia_nao_faz_chamada(stub):
    assert VoyageEmbedder(api_key="al-x").embed_documents([]) == []
    assert stub.calls == []


def test_vetor_de_tamanho_diferente_do_indice_e_recusado(stub):
    embedder = VoyageEmbedder(api_key="al-x", dimensions=256)

    with pytest.raises(ValueError, match="recriar o indice"):
        embedder.embed_documents(["um texto"])


def test_o_modelo_pedido_e_o_modelo_usado(stub):
    VoyageEmbedder(api_key="al-x", model="voyage-4-lite").embed_query("oi")

    assert stub.calls[0][1] == "voyage-4-lite"
