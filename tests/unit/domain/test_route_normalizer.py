import pytest

from engrama.domain.errors import InvalidRoute
from engrama.domain.services import RouteNormalizer
from engrama.domain.value_objects import HttpMethod, HttpRoute

normalizer = RouteNormalizer()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/api/v1/items/:id", "/api/v1/items/{id}"),  # Gin
        ("/api/v1/generate/batch/${jobId}", "/api/v1/generate/batch/{jobId}"),  # TypeScript
        ("/categories/$categoryId/questions", "/categories/{categoryId}/questions"),  # Dart
        ("/users/<int:user_id>", "/users/{user_id}"),  # Flask
        ("/emails/{email_id}", "/emails/{email_id}"),  # FastAPI
        ("/api/v1/emails?${query}", "/api/v1/emails"),
        ("/api/v1/corpus?${params.toString()}", "/api/v1/corpus"),
        ("/rodadas/${rodada.id}/export", "/rodadas/{rodada_id}/export"),
        ("https://phishingquest.example.com/api/v1/", "/api/v1"),
        ("api//v1///items/", "/api/v1/items"),
        ("", "/"),
    ],
)
def test_normaliza_os_estilos_das_quatro_stacks(raw, expected):
    assert normalizer.normalize(raw) == expected


def test_junta_prefixo_de_grupo_e_caminho_vazio():
    assert normalizer.join("api/v1/items", "") == "/api/v1/items"
    assert normalizer.join("/api/v1/researcher", "/rodadas") == "/api/v1/researcher/rodadas"


def test_monta_rota_canonica():
    assert normalizer.route("post", "/api/v1", "/game/answer") == HttpRoute(
        HttpMethod.POST, "/api/v1/game/answer"
    )


def test_metodo_desconhecido():
    with pytest.raises(InvalidRoute):
        normalizer.route("FETCH", "/x")
