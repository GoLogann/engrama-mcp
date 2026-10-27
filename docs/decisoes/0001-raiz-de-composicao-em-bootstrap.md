# ADR 0001 — Raiz de composição em `engrama/bootstrap/`

- **Status:** aceita (registrada depois, a partir do que já estava em `main`)
- **Data:** 27/10/2026

## Contexto

O plano previa o container de injeção de dependências em `src/engrama/container.py`. O container conhece as classes concretas de `infrastructure` e liga os casos de uso aos `entrypoints`, então só pode ser a camada mais externa. Além dele, a composição tem mais duas peças: `Settings` (lê o ambiente) e `main` (o ponto de entrada do script `engrama`).

## Decisão

As três peças ficam juntas em `engrama.bootstrap` (`settings.py`, `container.py`, `main.py`), a camada mais externa. O contrato de camadas em `pyproject.toml` fica `bootstrap` > `entrypoints | infrastructure` > `application` > `domain`. O script `engrama` aponta para `engrama.bootstrap.main:main`.

Isto é organização, não uma exigência do import-linter: ele aceita um módulo solto como camada (testado com `engrama.bootstrap.container` no topo, sem nenhuma exceção), então um `src/engrama/container.py` também teria funcionado.

## Alternativas consideradas

- `container.py` solto na raiz, como camada de um módulo só: funciona e é o que o plano descrevia. Deixaria `Settings` e `main` sem um lugar óbvio, e o nome `bootstrap` diz o que eles são.
- Container dentro de `infrastructure`: inverteria a dependência, porque a infraestrutura passaria a conhecer os entrypoints.

## Consequências

- Só `bootstrap` importa classes concretas de mais de uma camada. Um handler continua sem conhecer o adapter do Neo4j.
- Quem procurar `container.py` na raiz pelo plano não o encontra; `docs/arquitetura.md` descreve o caminho real.
- Reverter é mover três arquivos e trocar uma linha do contrato.
