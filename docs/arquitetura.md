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

**Regra de dependência:** uma camada só importa as que estão abaixo dela. `entrypoints` e `infrastructure` são irmãs independentes: um handler MCP recebe o caso de uso pronto e nunca importa o adapter do Neo4j. `domain` e `application` não importam frameworks nem drivers (Pydantic, pydantic-settings, dependency-injector, Typer, PyYAML, o driver do Neo4j, tree-sitter e detect-secrets).

As duas regras são verificadas pelo [import-linter](https://import-linter.readthedocs.io/) (`poetry run lint-imports`), configurado em `pyproject.toml` (decisão em [0002](decisoes/0002-contratos-de-camadas-no-pyproject-e-ci.md)). O CI (`.github/workflows/ci.yml`) roda lint, formatação, `lint-imports` e os testes, com um Neo4j descartável, em Python 3.12 e 3.13. Uma violação quebra o build.

## Onde cada coisa mora

| Camada | Pacote | Conteúdo |
| --- | --- | --- |
| Domínio | `engrama.domain.entities` | `Project`, `Repo`, `Module`, `Endpoint`, `DataStore`, `Concept`, `Doc`, `Decision`, `Chunk`, `Issue`, `Episode`, `Person`, `Edge` |
| Domínio | `engrama.domain.value_objects` | `Evidence`, `Provenance`, `Validity`, `NodeRef`, `HttpRoute`, `CallSite` |
| Domínio | `engrama.domain.services` | Lógica pura sem I/O: normalizar rotas, casar chamada com rota, cortar documento em pedaços, montar os pedaços de grafo de um repo |
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

Reingerir é idempotente (as regras de vigência estão no [ADR 0009](decisoes/0009-vigencia-das-arestas-e-ingestao-parcial.md)). Uma aresta de extração que não aparece numa rodada nova ganha `valid_to` e deixa de ser lida, mas continua no grafo. `valid_from` e `ingested_at` valem a primeira vez que o fato foi visto e não mudam nas reingestões seguintes.

Uma `CALLS` pertence ao repo cliente, e só existe se cliente e servidor entram na mesma rodada. Por isso `engrama ingest --repo X` traz também os clientes de X (as rotas deles podem ter mudado) e todos os servidores de cada repo que entrou (`Catalog.with_related`); a CLI lista o que entrou por relação. Se a rota some do servidor, a chamada do cliente fica sem destino e é fechada. Nós nunca são removidos nem fechados, só as arestas: um endpoint que sumiu continua como nó sem `EXPOSES` aberta, então toda consulta parte das arestas abertas.

Limitações conhecidas, registradas como diagnóstico quando aparecem:

- `include_router(..., prefix=...)` no FastAPI e `Any`/`Handle` no Gin não são extraídos. Nenhum dos quatro repos os usa hoje.
- `issue #N` vale para o repo do arquivo, salvo se logo depois (na mesma linha ou na linha de comentário seguinte) vier `do repo <nome>`, `do <nome>` ou `do backend`. Este último resolve pelo `consumes` do repo e só vale quando há exatamente um; com zero ou vários, a citação é ignorada e sai um diagnóstico. Qualquer outra forma de apontar para outro repo continua sendo lida como o repo do arquivo.
- Um caminho fora da forma canônica (o curinga `*filepath` do Gin, `$id.json` do Dart) vira diagnóstico e só aquela rota é ignorada; a ingestão segue.
- A relação entre repos vem de `consumes` em `config/repos.yaml`. Um repo que faz chamadas e não declara `consumes` não é relacionado a ninguém numa ingestão parcial; `engrama ingest` sem `--repo` sempre refaz tudo.
- Manifests de dependência e Kubernetes ainda não entram: a ontologia não tem nós para eles ([ADR 0008](decisoes/0008-adiar-kubernetes-e-manifestos-de-dependencia.md)).

## Camada de documentação

`engrama index-docs` roda o caso de uso `IndexDocuments`: lê os documentos de cada repo no commit do catálogo, mascara os segredos, corta o texto em pedaços e grava `Doc`, `Decision` e `Chunk` no Neo4j. `engrama search "..."` busca nesses pedaços e mostra a fonte de cada um; `engrama check-sources` mede quantas fontes esperadas pelas perguntas de ouro a busca encontra. As decisões estão no [ADR 0010](decisoes/0010-camada-de-documentacao.md).

| O que entra | O que fica de fora |
| --- | --- |
| `*.md`, `*.config` e o `package.json` da raiz | `data/`, `assets/`, `ios/`, `android/`, `macos/`, `windows/`, `linux/`, `web/` e diretórios de teste |

`docs/decisoes/`, `docs/decisions/`, `adr/` e `adrs/` viram `Decision`, com o `status` lido da linha "Status:" do documento; o resto vira `Doc`. O título sai do primeiro título do arquivo (ignorando `#` dentro de bloco de código) ou do nome dele.

Cada pedaço (`Chunk`) guarda a faixa de linhas de onde saiu, para a fonte ser citada como `repo/caminho:linha`, e a trilha de títulos até ele. O corte segue as seções do Markdown: seções curtas seguidas são juntadas até `ENGRAMA_CHUNK_MAX_CHARS` (1500), e seção maior que isso é cortada em limite de linha.

A máscara de segredos (`SecretScanner.redact`) roda aqui, antes de o texto virar nó: o que o grafo guarda é sempre a versão mascarada, e o relatório diz quantos valores foram mascarados em cada repo. A política está em [seguranca.md](seguranca.md).

A busca é híbrida, atrás da porta `KnowledgeIndex` (ADR 0011). Duas metades independentes:

| Metade | Como acha | Adapter |
| --- | --- | --- |
| Palavra | Índice de texto completo do Neo4j, analisador português | `Neo4jKnowledgeIndex` |
| Significado | Índice vetorial do Neo4j sobre embeddings da Voyage | `Neo4jKnowledgeIndex` + `VoyageEmbedder` |

Elas acham coisas diferentes: a primeira exige a palavra, a segunda entende que "migrations" e `flyway` falam do mesmo assunto. Os dois resultados se juntam por `ReciprocalRankFusion`, um serviço de domínio: a pontuação do Lucene e a similaridade de cosseno estão em escalas incomparáveis, então a fusão usa só a **posição** em cada lista.

O vetor não entra na entidade `Chunk`: é artefato de recuperação, não fato do domínio. Quem embute é a porta `Embedder` e quem grava é a `VectorStore`, chamadas por `IndexDocuments` **depois** da escrita do grafo — vetor de pedaço que não existe é ignorado, nunca cria nó.

As arestas da documentação de um repo têm `owner = "<repo>:docs"`, camada separada da estrutura: a aposentadoria de arestas é por dono (ADR 0009), então indexar documentos não encerra o que `engrama ingest` gravou, nem o contrário.

Limitações conhecidas:

- `DOCUMENTED_IN` só nasce de duas evidências diretas: o `README.md` da raiz documenta o repo, e uma rota escrita no texto documenta aquele endpoint. Ligar documento a módulo ou a conceito é leitura de conteúdo e vem com origem `llm`.
- A rota citada só casa com endpoint do mesmo repo: um documento do frontend que cita rota da API não gera aresta.
- `index-docs` depende de `ingest`: sem endpoints no grafo, ele indexa e avisa que nenhum era conhecido.
- A busca de hoje é só por palavra, então pergunta com vocabulário diferente do documento não acha a fonte (medição em `engrama check-sources`).

## Como estender

**Uma stack nova** (por exemplo, Spring): crie uma subclasse de `TreeSitterExtractor` em `engrama.infrastructure.extractors`, implemente as queries da stack, adicione trechos de código dela em `tests/unit/infrastructure/test_extractors.py` e acrescente a classe à lista `extractors` do container (`bootstrap/container.py`; decisão em [0003](decisoes/0003-extratores-registrados-no-container.md)).

**Outro provedor de LLM ou de embeddings:** implemente `LLMGateway` ou `Embedder` em `engrama.infrastructure`, rode a suíte de contrato da porta contra ele e troque o provider no container.

## Testes

| Pasta | O que testa | Precisa de |
| --- | --- | --- |
| `tests/unit` | Domínio, casos de uso (com fakes), extratores (trechos de código dentro do teste), CLI e o formato das perguntas de ouro | Nada |
| `tests/contracts` | A mesma suíte contra o fake e contra o adapter real: o grafo (Neo4j), a busca na documentação (índice de texto completo) e a árvore de fontes (repositório git local) | Neo4j para o grafo e a busca; sem ele, os casos `[neo4j]` são pulados |
| `tests/integration` | O `GitSourceRepository` sobre um repo git local, o filtro de segredos sobre as linhas reais dos clones e a leitura de documentos dos quatro repos | git; os clones em `.cache/repos` (criados por `engrama ingest`), e sem eles esses casos são pulados |
