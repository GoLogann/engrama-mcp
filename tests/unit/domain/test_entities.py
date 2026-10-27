import pytest

from engrama.domain.entities import (
    Concept,
    DataStore,
    DataStoreKind,
    Decision,
    Doc,
    Endpoint,
    Issue,
    Module,
    Person,
    Project,
    Repo,
    Stack,
)
from engrama.domain.errors import InvalidNode
from engrama.domain.value_objects import HttpMethod, HttpRoute, NodeKind, NodeRef


@pytest.mark.parametrize(
    ("node", "expected"),
    [
        (Project("phishforge", "PhishForge"), NodeRef(NodeKind.PROJECT, "phishforge")),
        (
            Repo("phishforge-api", "phishforge", "https://x", "815bd3a", Stack.PYTHON_FASTAPI),
            NodeRef(NodeKind.REPO, "phishforge-api"),
        ),
        (
            Module("phishforge-api", "app/domain/services"),
            NodeRef(NodeKind.MODULE, "phishforge-api:app/domain/services"),
        ),
        (
            Endpoint("phishing-quest-api", HttpRoute(HttpMethod.GET, "/api/v1/rankings")),
            NodeRef(NodeKind.ENDPOINT, "phishing-quest-api:GET /api/v1/rankings"),
        ),
        (
            DataStore("phishforge-api", DataStoreKind.QDRANT, "phishing_articles"),
            NodeRef(NodeKind.DATASTORE, "phishforge-api:qdrant:phishing_articles"),
        ),
        (Concept("pista", "Pista", ("cue",)), NodeRef(NodeKind.CONCEPT, "pista")),
        (
            Doc("phishforge-api", "docs/integracao_api.md", "Integracao"),
            NodeRef(NodeKind.DOC, "phishforge-api:docs/integracao_api.md"),
        ),
        (
            Decision("phishing-quest-api", "docs/decisoes/0001-path-registro-usuario.md", "Path"),
            NodeRef(
                NodeKind.DECISION, "phishing-quest-api:docs/decisoes/0001-path-registro-usuario.md"
            ),
        ),
        (Issue("phishforge-api", 7), NodeRef(NodeKind.ISSUE, "phishforge-api#7")),
        (Person("GoLogann", "Logan Cardoso"), NodeRef(NodeKind.PERSON, "GoLogann")),
    ],
)
def test_chave_natural_de_cada_familia(node, expected):
    assert node.ref == expected


def test_igualdade_e_por_identidade_nao_por_atributos():
    antes = Endpoint("r", HttpRoute(HttpMethod.GET, "/a"), handler="v1")
    depois = Endpoint("r", HttpRoute(HttpMethod.GET, "/a"), handler="v2")

    assert antes == depois
    assert len({antes, depois}) == 1


def test_modulo_exige_caminho_relativo_sem_barra_final():
    with pytest.raises(InvalidNode):
        Module("r", "app/services/")


def test_issue_exige_numero_positivo():
    with pytest.raises(InvalidNode):
        Issue("r", 0)
