# ADR 0008 — Adiar os extratores de Kubernetes e de manifestos de dependência

- **Status:** proposta (Logan confirma ou pede para implementar)
- **Data:** 27/10/2026

## Contexto

O plano da Fase 1 pedia, além dos parsers tree-sitter, extração de migrations Flyway, manifests Kubernetes e arquivos de dependência. Implementados: o compose e, como evidência do Postgres, os diretórios de migrations. Não implementados: os 11 arquivos de `phishing-quest-api/kubernetes/prod/` e `go.mod`, `package.json`, `pubspec.yaml` e `pyproject.toml`. A ontologia não tem nós para recurso de cluster nem para dependência, e criá-los muda o modelo de dados.

## Decisão

Adiar. Esses arquivos entram na Fase 2 como texto indexado e resumido, não como estrutura.

## Alternativas consideradas

- Criar os nós `Dependency` e `ClusterResource` agora: é trabalho de modelagem sem pergunta de ouro que dependa disso hoje.

## Consequências

- Duas perguntas de ouro dependem desses arquivos: **n18** (tecnologias do PhishForge: `README.md` e `package.json`) e **t12** (migrations e ferramenta: `migrate/flyway.config` e `flyway-prod.config`). A Fase 2 prevê indexar READMEs, `docs/` e ADRs; para responder essas duas, ela precisa incluir também esses arquivos de configuração.
- Reabrir se a Fase 5 mostrar que perguntas sobre dependências ou infraestrutura falham por falta de estrutura.
