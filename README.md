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
cp .env.example .env          # defina NEO4J_PASSWORD
poetry install
docker compose up -d neo4j
poetry run engrama --help
```

## Qualidade

```bash
poetry run pytest             # testes
poetry run ruff check .       # lint
poetry run lint-imports       # regra de dependência entre camadas
```

## Documentação

- [Fundamentação e plano](docs/fundamentacao.md): a revisão da literatura e as decisões de design.
- [Arquitetura do código](docs/arquitetura.md): camadas, portas e como estender.
