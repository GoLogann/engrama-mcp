# ADR 0002 — Contratos de camadas no `pyproject.toml` e CI

- **Status:** aceita
- **Data:** 27/10/2026

## Contexto

O plano pedia um arquivo `.importlinter` e dizia que "uma violação quebra o build". Até este ADR não havia CI, então nada quebrava build nenhum, e o contrato `forbidden` listava só `pydantic`, `pydantic_settings`, `dependency_injector`, `typer` e `yaml`, embora `docs/arquitetura.md` falasse em "drivers".

## Decisão

- A configuração fica em `[tool.importlinter]` no `pyproject.toml`: o import-linter a lê de lá, e há um arquivo de configuração a menos para manter.
- O contrato `forbidden` passa a incluir `neo4j`, `tree_sitter`, `tree_sitter_language_pack` e `detect_secrets`. Cada fase soma os pacotes que instala (`anthropic`, `voyageai`, `graphiti_core`, `mcp`, `networkx`) ao mesmo tempo que os adiciona às dependências.
- `.github/workflows/ci.yml` roda `ruff check`, `ruff format --check`, `lint-imports` e `pytest` em Python 3.12 e 3.13, com um serviço `neo4j:5.26-community` descartável para os testes de contrato.

## Alternativas consideradas

- Manter `.importlinter`: equivalente, só mais um arquivo.
- Confiar no hábito de rodar `poetry run lint-imports` à mão: foi o que existia, e o contrato incompleto passou despercebido.

## Consequências

- Os testes que dependem dos clones em `.cache/repos` são pulados no CI, porque o CI não roda `engrama ingest`.
- A senha do Neo4j no workflow vale só dentro do container do job.
