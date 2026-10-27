from engrama.domain.services import CallRouteMatcher
from engrama.domain.value_objects import Evidence, HttpMethod, HttpRoute
from engrama.domain.value_objects.code_facts import CallSite, DeclaredRoute

C = "a" * 40


def declared(repo: str, method: HttpMethod, path: str) -> DeclaredRoute:
    return DeclaredRoute(
        repo, "api", HttpRoute(method, path), Evidence.in_code(repo, "api/r.py", C, 1)
    )


def call(repo: str, method: HttpMethod, path: str, line: int = 1) -> CallSite:
    return CallSite(
        repo, "src", HttpRoute(method, path), Evidence.in_code(repo, "src/s.ts", C, line)
    )


FORGE_CUES = declared("forge-api", HttpMethod.GET, "/api/v1/cues")
QUEST_CUES = declared("quest-api", HttpMethod.GET, "/api/v1/cues")
BATCH = declared("forge-api", HttpMethod.GET, "/api/v1/generate/batch/{job_id}")


def test_casa_ignorando_nome_de_parametro():
    report = CallRouteMatcher({}).match(
        [call("front", HttpMethod.GET, "/api/v1/generate/batch/{jobId}")], [BATCH]
    )

    assert [m.route for m in report.matches] == [BATCH]
    assert report.routes_without_callers == ()


def test_rota_em_duas_apis_e_ambigua_sem_consumes():
    report = CallRouteMatcher({}).match(
        [call("front", HttpMethod.GET, "/api/v1/cues")], [FORGE_CUES, QUEST_CUES]
    )

    assert report.matches == ()
    assert report.ambiguous_calls[0][1] == (FORGE_CUES, QUEST_CUES)


def test_consumes_resolve_a_ambiguidade():
    report = CallRouteMatcher({"front": ["forge-api"]}).match(
        [call("front", HttpMethod.GET, "/api/v1/cues")], [FORGE_CUES, QUEST_CUES]
    )

    assert [m.route for m in report.matches] == [FORGE_CUES]
    assert report.routes_without_callers == (QUEST_CUES,)


def test_metodo_diferente_nao_casa():
    report = CallRouteMatcher({}).match(
        [call("front", HttpMethod.POST, "/api/v1/cues")], [FORGE_CUES]
    )

    assert len(report.unmatched_calls) == 1


def test_cliente_nao_casa_com_rota_do_proprio_repo():
    own = declared("front", HttpMethod.GET, "/api/v1/cues")

    report = CallRouteMatcher({}).match([call("front", HttpMethod.GET, "/api/v1/cues")], [own])

    assert len(report.unmatched_calls) == 1
