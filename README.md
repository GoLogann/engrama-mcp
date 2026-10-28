# engrama-mcp

Cérebro de conhecimento em grafo dos projetos do LABit-UFPA, servido por um servidor MCP.

Qualquer pessoa pergunta sobre os projetos (pelo Claude Code ou pelo Claude app/web) e recebe uma resposta com a fonte: arquivo e linha, documento, ou episódio com autor e data. O grafo tem três camadas:

| Camada | O que guarda | De onde vem |
| --- | --- | --- |
| Estrutura | Repos, módulos, rotas, chamadas, bancos, infraestrutura | Extração determinística do código (tree-sitter) |
| Documentação | READMEs, docs, ADRs, resumos simples e técnicos | Indexação e resumos por LLM |
| Experiência | Decisões, aprendizados, problemas e reflexões | Pessoas, no momento em que acontecem |

A PoC cobre quatro repositórios: `phishforge-api`, `phishforge-frontend`, `phishing-quest-api` e `phishing_quest` (commits fixados em [config/repos.yaml](config/repos.yaml)).

## Status

PoC em andamento. Fases e portões de qualidade em [docs/fundamentacao.md](docs/fundamentacao.md#poc-com-os-quatro-repositórios).

## Rodando localmente

Requisitos: Python 3.12 ou 3.13, [Poetry](https://python-poetry.org/) 2.x e Docker.

```bash
cp .env.example .env              # defina NEO4J_PASSWORD (e VOYAGE_API_KEY, ver abaixo)
poetry install
docker compose up -d neo4j
poetry run engrama ingest         # clona os 4 repos em .cache/ e grava a estrutura no Neo4j
poetry run engrama check-structure  # Portão 1: confere com o groundtruth
poetry run engrama index-docs     # indexa README, docs/, ADRs e configuração
poetry run engrama search "onde ficam as migrations?"   # busca com a fonte de cada pedaço
poetry run engrama check-sources  # quanto da fonte esperada a busca encontra
```

O grafo fica no Neo4j Browser em http://localhost:7474.

### Chave de embeddings (opcional, mas recomendada)

A busca ordena por **significado** quando há `VOYAGE_API_KEY`, e por **palavra** quando não há. Os dois modos funcionam; o primeiro acha mais: 91% das fontes esperadas pelas perguntas de ouro contra 82%, medido no [ADR 0011](docs/decisoes/0011-busca-por-significado-e-reserva-por-palavra.md). `engrama check-sources` sempre diz por qual dos dois mediu.

A chave sai do MongoDB Atlas, em **AI Model APIs → Create model API key** ([documentação](https://www.mongodb.com/docs/voyageai/management/api-keys/)); não é preciso criar cluster nem ser cliente pago de banco. O corpus dos quatro repos tem cerca de 34 mil tokens, contra 200 milhões gratuitos por conta.

Sem forma de pagamento cadastrada a conta fica limitada a 3 requisições e 10 mil tokens por minuto. Nesse teto, `index-docs` leva alguns minutos e cada busca é uma chamada de rede; o adapter espera e tenta de novo em vez de falhar.

## Qualidade

```bash
poetry run pytest             # testes; os de contrato usam o Neo4j se ele estiver de pé
poetry run ruff check .       # lint
poetry run lint-imports       # regra de dependência entre camadas
```

## Documentação

- [Fundamentação e plano](docs/fundamentacao.md): a revisão da literatura e as decisões de design.
- [Arquitetura do código](docs/arquitetura.md): camadas, portas e como estender.
- [Ontologia do grafo](docs/ontologia.md): nós, arestas e propriedades obrigatórias.
- [Decisões de arquitetura](docs/decisoes/): por que o código diverge do plano em cada ponto.
- [Segredos e dados sensíveis](docs/seguranca.md): o que nunca entra no grafo e o que nunca sai dele.
- [Perguntas de ouro](eval/golden_questions.yaml) e [groundtruth estrutural](eval/structure_groundtruth.yaml): a base da avaliação.
