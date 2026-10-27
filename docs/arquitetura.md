# Arquitetura do código

O engrama segue Clean Architecture: o domínio não conhece banco, LLM nem protocolo, e cada detalhe técnico fica atrás de uma porta que o bootstrap liga a um adapter.

## Camadas

```
bootstrap        raiz de composição: settings, container de DI, main
   │
   ├── entrypoints      bordas finas: MCP, CLI, webhook HTTP
   └── infrastructure   adapters: Neo4j, tree-sitter, Anthropic, Voyage, Graphiti, git
          │
      application       portas (abc.ABC), casos de uso, DTOs
          │
        domain          entidades, value objects, serviços de domínio
```

**Regra de dependência:** uma camada só importa as que estão abaixo dela. `entrypoints` e `infrastructure` são irmãs independentes: um handler MCP recebe o caso de uso pronto e nunca importa o adapter do Neo4j. `domain` e `application` não importam frameworks (Pydantic, dependency-injector, Typer, PyYAML, drivers).

As duas regras são verificadas pelo [import-linter](https://import-linter.readthedocs.io/) (`poetry run lint-imports`), configurado em `pyproject.toml`. Uma violação quebra o build.

## Onde cada coisa mora

| Camada | Pacote | Conteúdo |
| --- | --- | --- |
| Domínio | `engrama.domain.entities` | `Project`, `Repo`, `Module`, `Endpoint`, `DataStore`, `Concept`, `Doc`, `Decision`, `Episode`, `Person`, `Edge` |
| Domínio | `engrama.domain.value_objects` | `Evidence`, `Provenance`, `Validity`, `NodeRef`, `HttpRoute`, `CallSite` |
| Domínio | `engrama.domain.services` | Lógica pura sem I/O, como normalizar rotas e casar chamadas com rotas |
| Aplicação | `engrama.application.ports` | Interfaces que os casos de uso exigem |
| Aplicação | `engrama.application.use_cases` | Uma classe por caso de uso, com `execute()` |
| Infraestrutura | `engrama.infrastructure.*` | Um adapter por porta |
| Entrypoints | `engrama.entrypoints.{mcp,cli,http}` | Tradução entre o protocolo e o caso de uso |
| Bootstrap | `engrama.bootstrap` | `Settings`, `Container` (dependency-injector), `main` |

## Modelo de domínio

- Value objects são imutáveis (`@dataclass(frozen=True, slots=True)`).
- Entidades carregam as regras do negócio. Uma `Edge` não existe sem `Provenance` e `Validity`, então toda aresta tem origem, evidência e validade no tempo. Um `Episode` nunca é editado: ao ser substituído, o domínio devolve o antigo com `valid_to` fechado e o novo ligado por `SUPERSEDES`.
- Pydantic aparece só nas bordas: DTOs das tools MCP, schemas de saída estruturada do LLM e configuração.

## SOLID

| Princípio | Como aparece |
| --- | --- |
| Responsabilidade única | Um caso de uso por classe; handlers MCP e CLI só traduzem; um extrator por stack |
| Aberto/fechado | Stack nova = um `CodeExtractor` novo registrado no container; o pipeline de ingestão não muda |
| Substituição de Liskov | Fakes em memória e adapters reais passam pela mesma suíte de contrato da porta (`tests/contracts/`) |
| Segregação de interfaces | `GraphReader` separado de `GraphWriter`; `EpisodeRepository` só acrescenta, sem update nem delete |
| Inversão de dependência | Casos de uso recebem portas no construtor; só o `Container` conhece classes concretas |

## Extração da camada de estrutura

`engrama ingest` roda o caso de uso `BuildStructuralGraph`: leva cada repo ao commit do catálogo, aplica os extratores que valem para ele, casa as chamadas com as rotas de todos os repos e grava tudo no Neo4j numa transação. `engrama check-structure` confere o grafo gravado com `eval/structure_groundtruth.yaml` (Portão 1: rotas, chamadas e bancos).

| Extrator | Stack | O que lê |
| --- | --- | --- |
| `FastApiExtractor` | Python | `@router.<método>("/caminho")` + `APIRouter(prefix=...)` do mesmo arquivo |
| `GinExtractor` | Go | `grupo.GET("/caminho", handler)`, com prefixos de `router.Group(...)` encadeados |
| `ReactServiceExtractor` | TypeScript | chamadas a `request`/`requestBlob`, resolvendo constantes, template strings e ternários; `method` do segundo argumento, padrão GET |
| `FlutterExtractor` | Dart | `buildUrl(url: ...)` em `lib/`, com o método da chamada HTTP que usa a mesma variável |
| `ComposeExtractor` | todas | bancos no compose da raiz: Postgres com `POSTGRES_DB`, Qdrant, Redis; migrations Flyway como evidência. Para o Qdrant, o nome é a coleção lida do `COLLECTION_NAME` do código (a linha vira a 2ª evidência); sem ela, vale o nome do serviço e sai um diagnóstico |
| `IssueReferenceExtractor` | todas | `issue #7`, `issues #12 e #13` e `<repo-do-catálogo> #5` em código |

O que a extração não deduz do código fica declarado em `config/repos.yaml`, com a evidência: qual API cada cliente consome (`consumes`) e o caminho base das chamadas (`base_path`). As duas coisas vêm de variável de ambiente nos repos.

Reingerir é idempotente. Uma aresta de extração que não aparece numa rodada nova ganha `valid_to` e deixa de ser lida, mas continua no grafo. `valid_from` e `ingested_at` valem a primeira vez que o fato foi visto e não mudam nas reingestões seguintes.

Uma `CALLS` pertence ao repo cliente, e só existe se cliente e servidor entram na mesma rodada. Por isso `engrama ingest --repo X` traz também os clientes de X (as rotas deles podem ter mudado) e todos os servidores de cada repo que entrou (`Catalog.with_related`); a CLI lista o que entrou por relação. Se a rota some do servidor, a chamada do cliente fica sem destino e é fechada. Nós nunca são removidos nem fechados, só as arestas: um endpoint que sumiu continua como nó sem `EXPOSES` aberta, então toda consulta parte das arestas abertas.

Limitações conhecidas, registradas como diagnóstico quando aparecem:

- `include_router(..., prefix=...)` no FastAPI e `Any`/`Handle` no Gin não são extraídos. Nenhum dos quatro repos os usa hoje.
- `issue #N` sempre aponta para o repo do arquivo. No frontend, "issue #7 do backend" vira a issue #7 do frontend.
- A relação entre repos vem de `consumes` em `config/repos.yaml`. Um repo que faz chamadas e não declara `consumes` não é relacionado a ninguém numa ingestão parcial; `engrama ingest` sem `--repo` sempre refaz tudo.
- Manifests de dependência e Kubernetes ainda não entram: a ontologia não tem nós para eles.

## Como estender

**Uma stack nova** (por exemplo, Spring): crie uma subclasse de `TreeSitterExtractor` em `engrama.infrastructure.extractors`, implemente as queries da stack, adicione fixtures em `tests/fixtures/` e registre a classe no `ExtractorRegistry` do container.

**Outro provedor de LLM ou de embeddings:** implemente `LLMGateway` ou `Embedder` em `engrama.infrastructure`, rode a suíte de contrato da porta contra ele e troque o provider no container.

## Testes

| Pasta | O que testa | Precisa de |
| --- | --- | --- |
| `tests/unit` | Domínio e casos de uso, com fakes | Nada |
| `tests/contracts` | Cada porta contra o fake e contra o adapter real | Neo4j para os adapters reais |
| `tests/integration` | Adapters reais de ponta a ponta | `docker compose up -d neo4j` |
