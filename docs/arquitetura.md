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

## Como estender

**Uma stack nova** (por exemplo, Spring): crie uma subclasse de `TreeSitterExtractor` em `engrama.infrastructure.extractors`, implemente as queries da stack, adicione fixtures em `tests/fixtures/` e registre a classe no `ExtractorRegistry` do container.

**Outro provedor de LLM ou de embeddings:** implemente `LLMGateway` ou `Embedder` em `engrama.infrastructure`, rode a suíte de contrato da porta contra ele e troque o provider no container.

## Testes

| Pasta | O que testa | Precisa de |
| --- | --- | --- |
| `tests/unit` | Domínio e casos de uso, com fakes | Nada |
| `tests/contracts` | Cada porta contra o fake e contra o adapter real | Neo4j para os adapters reais |
| `tests/integration` | Adapters reais de ponta a ponta | `docker compose up -d neo4j` |
