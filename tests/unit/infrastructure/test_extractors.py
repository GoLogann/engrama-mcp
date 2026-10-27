from textwrap import dedent

from engrama.application.dto.ingestion import RepositorySpec
from engrama.domain.entities import Repo, Stack
from engrama.domain.services import RouteNormalizer
from engrama.infrastructure.extractors import (
    ComposeExtractor,
    FastApiExtractor,
    FlutterExtractor,
    GinExtractor,
    IssueReferenceExtractor,
    ReactServiceExtractor,
)
from tests.fakes.sources import InMemorySourceTree

C = "c" * 40
N = RouteNormalizer()


def run(extractor, stack: Stack, files: dict[str, str], name="repo", base_path=""):
    repo = Repo(name, "p", f"https://x/{name}", C, stack)
    spec = RepositorySpec(repo, base_path=base_path)
    assert extractor.supports(spec)
    return extractor.extract(
        InMemorySourceTree(repo, {k: dedent(v) for k, v in files.items()}), spec
    )


def routes(facts):
    return [(str(r.route), r.evidence.path, r.evidence.line) for r in facts.routes]


def calls(facts):
    return [(str(c.route), c.evidence.path, c.evidence.line) for c in facts.calls]


def test_fastapi_soma_prefixo_do_router_e_ignora_testes():
    facts = run(
        FastApiExtractor(N),
        Stack.PYTHON_FASTAPI,
        {
            "app/api/expert.py": """\
                from fastapi import APIRouter
                router = APIRouter(prefix="/api/v1/expert", tags=["expert"])

                @router.post("/session", response_model=X)
                @inject
                async def criar_sessao():
                    ...

                @router.get("/itens/{ordem}")
                async def item(ordem: int):
                    ...
            """,
            "app/api/generator.py": """\
                app = APIRouter()

                @app.delete("/api/v1/emails/{email_id}")
                def apagar(email_id): ...
            """,
            "tests/test_api.py": """\
                @router.get("/nao-conta")
                def t(): ...
            """,
        },
    )

    assert routes(facts) == [
        ("POST /api/v1/expert/session", "app/api/expert.py", 4),
        ("GET /api/v1/expert/itens/{ordem}", "app/api/expert.py", 9),
        ("DELETE /api/v1/emails/{email_id}", "app/api/generator.py", 3),
    ]
    assert [r.handler for r in facts.routes] == ["criar_sessao", "item", "apagar"]
    assert facts.modules == {"app/api"}


def test_fastapi_avisa_include_router_com_prefixo():
    facts = run(
        FastApiExtractor(N),
        Stack.PYTHON_FASTAPI,
        {"main.py": 'app.include_router(router, prefix="/v2")\n'},
    )

    assert "include_router com prefix" in facts.diagnostics[0]


def test_gin_encadeia_grupos_e_converte_parametros():
    facts = run(
        GinExtractor(N),
        Stack.GO_GIN,
        {
            "adapter/http/router/item_router.go": """\
                package router

                func SetupItemRoutes(router *gin.Engine, h *handler.H, auth gin.HandlerFunc) {
                \titemGroup := router.Group("api/v1/items")
                \titemGroup.Use(auth)
                \t{
                \t\titemGroup.GET("", h.ListItems)
                \t\titemGroup.GET("/:id", auth, h.GetItem)
                \t}
                \tadmin := itemGroup.Group("/admin")
                \tadmin.POST("/:id/publish", h.Publish)
                \trouter.POST("api/v1/item-cues", h.Associate)
                \trouter.Any("/x", h.X)
                }
            """,
            "adapter/http/router/item_router_test.go": (
                'func T(router *gin.Engine) { router.GET("/t", f) }'
            ),
        },
    )

    assert routes(facts) == [
        ("GET /api/v1/items", "adapter/http/router/item_router.go", 7),
        ("GET /api/v1/items/{id}", "adapter/http/router/item_router.go", 8),
        ("POST /api/v1/items/admin/{id}/publish", "adapter/http/router/item_router.go", 11),
        ("POST /api/v1/item-cues", "adapter/http/router/item_router.go", 12),
    ]
    assert facts.routes[1].handler == "h.GetItem"
    assert "Any" in facts.diagnostics[0]


def test_react_resolve_constante_template_ternario_e_metodo():
    facts = run(
        ReactServiceExtractor(N),
        Stack.TYPESCRIPT_REACT,
        {
            "src/services/researcherApiService.ts": """\
                const P = '/api/v1/researcher'
                export const listar = (k: string) => request<R[]>(`${P}/rodadas`, com(k))
                export const criar = (k: string, body: B) =>
                  request<R>(`${P}/rodadas`, { ...com(k), method: 'POST', body })
                export function exportar(id: string) {
                  return requestBlob(`${P}/rodadas/${id}/export?${params.toString()}`, com(k))
                }
            """,
            "src/services/apiService.ts": """\
                export function listarEmails(q: string) {
                  return request<L>(q ? `/api/v1/emails?${q}` : '/api/v1/emails', { signal })
                }
                export const outra = () => fetch('/nao-e-cliente')
            """,
            "src/services/apiService.test.ts": "request('/api/v1/teste')\n",
        },
    )

    assert calls(facts) == [
        ("GET /api/v1/emails", "src/services/apiService.ts", 2),
        ("GET /api/v1/researcher/rodadas", "src/services/researcherApiService.ts", 2),
        ("POST /api/v1/researcher/rodadas", "src/services/researcherApiService.ts", 4),
        ("GET /api/v1/researcher/rodadas/{id}/export", "src/services/researcherApiService.ts", 6),
    ]


def test_flutter_resolve_constante_base_path_e_metodo_da_chamada():
    facts = run(
        FlutterExtractor(N),
        Stack.DART_FLUTTER,
        {
            "lib/app/data/repositories/login_repository.dart": """\
                final class LoginRepository extends RequestRepository {
                  static const String loginUrl = '/users/login';

                  Future<ValidResponse> login() async {
                    final url = apiHelpers.buildUrl(url: loginUrl);
                    final body = {'email': email};
                    try {
                      final response = await client.post(url, body, headers: {});
                    } catch (e) {}
                  }

                  Future<List> perguntas(String categoryId) async {
                    final url = _apiHelpers.buildUrl(url: '/categories/$categoryId/questions');
                    final response = await _client.get(url);
                  }
                }
            """,
            "test/widget_test.dart": "final url = h.buildUrl(url: '/x');\n",
        },
        base_path="/api/v1",
    )

    assert calls(facts) == [
        ("POST /api/v1/users/login", "lib/app/data/repositories/login_repository.dart", 5),
        (
            "GET /api/v1/categories/{categoryId}/questions",
            "lib/app/data/repositories/login_repository.dart",
            13,
        ),
    ]


def test_compose_so_conta_postgres_com_banco_e_soma_migrations():
    facts = run(
        ComposeExtractor(),
        Stack.PYTHON_FASTAPI,
        {
            "docker-compose.yml": """\
                services:
                  db:
                    image: postgres:16.4
                    environment:
                      POSTGRES_DB: forge
                  vectors:
                    image: qdrant/qdrant:v1.18.0
                  export:
                    image: postgres:16.4
                    environment:
                      - PGHOST=db
            """,
            "migrate/changelogs/V1__init.sql": "create table x();",
        },
    )

    stores = [(d.kind, d.name, [str(e) for e in d.evidence]) for d in facts.datastores]
    assert stores == [
        (
            "postgres",
            "forge",
            ["repo/docker-compose.yml:2@ccccccc", "repo/migrate/changelogs@ccccccc"],
        ),
        ("qdrant", "vectors", ["repo/docker-compose.yml:6@ccccccc"]),
    ]


def test_issues_do_proprio_repo_e_de_outro_repo_do_catalogo():
    facts = run(
        IssueReferenceExtractor(["forge-api", "quest-api"]),
        Stack.GO_GIN,
        {
            "core/service/draft.go": """\
                // payload aninhado desde a issue #68
                // para o lado Python (forge-api #5 e #6) gerar os canais
                // cor #fff nao e issue; issues #12, #13
            """,
            "tests/x_test.go": "// issue #99\n",
        },
        name="quest-api",
    )

    found = [(i.issue_repo, i.number, i.evidence.line) for i in facts.issues]
    assert found == [
        ("quest-api", 68, 1),
        ("forge-api", 5, 2),
        ("forge-api", 6, 2),
        ("quest-api", 12, 3),
        ("quest-api", 13, 3),
    ]
