from engrama.domain.entities import Endpoint
from engrama.domain.services import RouteMentionMatcher
from engrama.domain.value_objects import Evidence, HttpMethod, HttpRoute
from engrama.domain.value_objects.document_facts import RouteMention

C = "c" * 40
QUEST = "phishing-quest-api"
FORGE = "phishforge-api"


def endpoint(repo, method, path):
    return Endpoint(repo, HttpRoute(HttpMethod(method), path))


def mention(repo, method, path, doc="docs/api.md", line=10):
    return RouteMention(
        repo, doc, HttpRoute(HttpMethod(method), path), Evidence.in_code(repo, doc, C, line)
    )


def test_casa_a_rota_escrita_igual_a_do_grafo():
    report = RouteMentionMatcher().match(
        [mention(FORGE, "POST", "/api/v1/generate/batch")],
        [endpoint(FORGE, "POST", "/api/v1/generate/batch")],
    )

    assert len(report.matches) == 1
    assert report.matches[0].endpoint.repo == FORGE
    assert report.unmatched == ()


def test_casa_rota_escrita_sem_o_prefixo_do_servidor():
    report = RouteMentionMatcher().match(
        [mention(QUEST, "POST", "/users/register", doc="docs/decisoes/0001.md")],
        [endpoint(QUEST, "POST", "/api/v1/users/register")],
    )

    assert [m.endpoint.key for m in report.matches] == [f"{QUEST}:POST /api/v1/users/register"]


def test_nome_do_parametro_nao_conta():
    report = RouteMentionMatcher().match(
        [mention(FORGE, "GET", "/api/v1/emails/{id}")],
        [endpoint(FORGE, "GET", "/api/v1/emails/{email_id}")],
    )

    assert len(report.matches) == 1


def test_rota_de_outro_repo_nao_e_citacao_sobre_ele():
    report = RouteMentionMatcher().match(
        [mention(FORGE, "GET", "/api/v1/cues")],
        [endpoint(QUEST, "GET", "/api/v1/cues")],
    )

    assert report.matches == ()
    assert len(report.unmatched) == 1


def test_sufixo_que_serve_a_dois_endpoints_fica_ambiguo():
    report = RouteMentionMatcher().match(
        [mention(FORGE, "GET", "/items")],
        [endpoint(FORGE, "GET", "/api/v1/items"), endpoint(FORGE, "GET", "/api/v2/items")],
    )

    assert report.matches == ()
    assert len(report.ambiguous) == 1
    assert len(report.ambiguous[0][1]) == 2


def test_sufixo_so_encaixa_em_limite_de_segmento():
    report = RouteMentionMatcher().match(
        [mention(FORGE, "GET", "/users")],
        [endpoint(FORGE, "GET", "/api/v1/myusers")],
    )

    assert len(report.unmatched) == 1


def test_metodo_diferente_nao_casa():
    report = RouteMentionMatcher().match(
        [mention(FORGE, "DELETE", "/api/v1/emails/{id}")],
        [endpoint(FORGE, "GET", "/api/v1/emails/{id}")],
    )

    assert len(report.unmatched) == 1


def test_rota_exata_vence_o_sufixo():
    report = RouteMentionMatcher().match(
        [mention(FORGE, "GET", "/api/v1/items")],
        [endpoint(FORGE, "GET", "/api/v1/items"), endpoint(FORGE, "GET", "/v2/api/v1/items")],
    )

    assert [m.endpoint.route.path for m in report.matches] == ["/api/v1/items"]
