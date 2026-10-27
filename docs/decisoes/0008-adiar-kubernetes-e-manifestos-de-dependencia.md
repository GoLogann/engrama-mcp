# ADR 0008 — Adiar os extratores de Kubernetes e de manifestos de dependência

- **Status:** aceita por Logan em 27/10/2026: adiar até a Fase 5 e só então decidir
- **Data:** 27/10/2026

## Contexto

O plano da Fase 1 pedia, além dos parsers tree-sitter, extração de migrations Flyway, manifests Kubernetes e arquivos de dependência. Implementados: o compose e, como evidência do Postgres, os diretórios de migrations. Não implementados: os 11 arquivos de `phishing-quest-api/kubernetes/prod/` e `go.mod`, `package.json`, `pubspec.yaml` e `pyproject.toml`. A ontologia não tem nós para recurso de cluster nem para dependência, e criá-los muda o modelo de dados.

## Decisão

Adiar. Não implementar agora e não criar os nós. A decisão de implementar ou não fica para depois da Fase 5, com a avaliação medida, em vez de ser tomada antes de saber se faz falta.

**Gatilho para reabrir:** na Fase 5, se perguntas de ouro sobre dependências, infraestrutura ou migrations (hoje n18 e t12) errarem por falta de estrutura, e não por falha de busca ou de resumo, este ADR é reaberto e os extratores entram. Se o Portão 2 passar sem eles, o adiamento vira definitivo.

## Alternativas consideradas

- Criar os nós `Dependency` e `ClusterResource` agora: é trabalho de modelagem sem pergunta de ouro que dependa disso hoje.

## Consequências

- Duas perguntas de ouro dependem desses arquivos: **n18** (tecnologias do PhishForge: `README.md` e `package.json`) e **t12** (migrations e ferramenta: `migrate/flyway.config` e `flyway-prod.config`). A Fase 2 prevê indexar READMEs, `docs/` e ADRs; para tentar responder essas duas sem estrutura, ela precisa incluir também esses arquivos de configuração. Sem isso, as duas vão falhar por um motivo que o adiamento não justifica.
- Se o gatilho disparar, serão necessários nós novos na ontologia, extratores novos e testes de contrato; `docs/ontologia.md` e `docs/arquitetura.md` mudam junto.
