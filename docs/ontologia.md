# Ontologia do grafo

O grafo tem 11 famílias de nó em três camadas e 10 tipos de aresta. Toda aresta e todo episódio carregam origem, evidência, confiança e validade no tempo. As regras abaixo estão codificadas no domínio (`engrama.domain`) e valem por construção: um objeto que as viola não chega a existir.

## Nós

Cada nó tem uma chave natural única, gravada na propriedade `key` (constraints em `src/engrama/infrastructure/neo4j/schema.cypher`).

| Nó | Camada | Chave natural | Exemplo |
| --- | --- | --- | --- |
| `Project` | Estrutura | `slug` | `phishforge` |
| `Repo` | Estrutura | `nome` | `phishforge-api` |
| `Module` | Estrutura | `repo:caminho` | `phishforge-api:app/domain/services` |
| `Endpoint` | Estrutura | `repo:MÉTODO caminho` | `phishing-quest-api:GET /api/v1/rankings` |
| `DataStore` | Estrutura | `repo:tipo:nome` | `phishforge-api:qdrant:phishing_articles` |
| `Concept` | Documentação | `slug` | `pista` (alias `cue`) |
| `Doc` | Documentação | `repo:caminho` | `phishforge-api:docs/integracao_api.md` |
| `Decision` | Documentação | `repo:caminho` | `phishing-quest-api:docs/decisoes/0001-path-registro-usuario.md` |
| `Issue` | Documentação | `repo#número` | `phishforge-api#7` |
| `Episode` | Experiência | `id` (UUID) | |
| `Person` | Experiência | login do GitHub | `GoLogann` |

Decisões de modelagem:

- **`Module` é um diretório**, não um arquivo. É o nível em que resumos fazem sentido; o arquivo e a linha exatos ficam na evidência de cada aresta.
- **`Issue` entrou na ontologia** porque a aresta `REFERENCES_ISSUE` do doc de fundamentação precisava de um alvo. O código dos quatro repos cita issues com frequência (`issue #7`, `#36`).
- **`Endpoint` guarda a rota na forma canônica:** começa com `/`, sem barra final nem query string, parâmetros como `{nome}`. `:id` (Gin), `${id}` (TypeScript) e `$id` (Dart) são convertidos na extração. Ao casar chamada com rota, os nomes dos parâmetros são ignorados (`HttpRoute.shape`).

## Arestas

| Aresta | De → para | Origens permitidas |
| --- | --- | --- |
| `EXPOSES` | `Module` → `Endpoint` | extração |
| `CALLS` | `Module` → `Endpoint` | extração |
| `STORES_IN` | `Repo`, `Module` → `DataStore` | extração |
| `PART_OF` | `Module` → `Module`/`Repo`; `Repo` → `Project`; `DataStore`, `Doc`, `Decision` → `Repo` | extração |
| `DOCUMENTED_IN` | `Project`, `Repo`, `Module`, `Endpoint`, `DataStore` → `Doc`, `Decision` | extração, documento, LLM |
| `MENTIONS_CONCEPT` | `Doc`, `Decision`, `Module`, `Endpoint`, `Issue`, `Episode` → `Concept` | documento, LLM, pessoa |
| `REFERENCES_ISSUE` | `Module`, `Doc`, `Decision`, `Episode` → `Issue` | extração, pessoa |
| `ABOUT` | `Episode` → qualquer nó, exceto `Episode` e `Person` | pessoa, documento |
| `AUTHORED_BY` | `Episode` → `Person` | pessoa, documento |
| `SUPERSEDES` | `Episode` → `Episode` | pessoa, documento |

As quatro arestas estruturais só vêm da extração determinística (princípio 1 do doc). O LLM resume e liga conceitos, mas nunca cria `CALLS`.

## Propriedades obrigatórias

| Propriedade | Onde | Regra |
| --- | --- | --- |
| `source` | arestas e episódios | `extraction`, `document`, `llm` ou `person` |
| `evidence` | arestas e episódios | repo, arquivo, linha e commit, ou o link do documento. Só `person` pode ficar sem evidência externa: o episódio, com autor e data, é a evidência |
| `confidence` | arestas e episódios | `high` só para extração (obrigatório) e pessoa; `llm` nunca chega a `high` |
| `valid_from`, `valid_to`, `ingested_at` | arestas e episódios | datas com fuso; `valid_to` nulo = vale hoje; nada é apagado, o que deixa de valer ganha `valid_to` |
| `author` | episódios | um `Person`, via `AUTHORED_BY` |

## Episódios

O formato segue o doc de fundamentação:

```yaml
tipo: aprendizado        # aprendizado | decisao | problema | reflexao
sobre: [phishforge-api:app/domain/services]
texto: o que aprendemos e por quê
autor: preenchido pelo login
data: preenchida pelo sistema
substitui: episódio anterior, se houver
```

Regras:

- Um episódio nunca é editado. Substituir devolve o antigo com `valid_to` e um sucessor ligado por `SUPERSEDES`.
- Um episódio já substituído não é substituído de novo: o histórico é linear.
- `sobre` precisa de pelo menos um nó, e esse nó não pode ser outro episódio nem uma pessoa.
- Episódios semeados de documentos existentes (análises, ADRs) usam `valid_from` com a data do documento e origem `document`.
