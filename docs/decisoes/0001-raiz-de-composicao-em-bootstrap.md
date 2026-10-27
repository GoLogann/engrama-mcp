# ADR 0001 — Raiz de composição em `engrama/bootstrap/`

- **Status:** aceita (registrada depois, a partir do que já estava em `main`)
- **Data:** 27/10/2026

## Contexto

O plano previa o container de injeção de dependências em `src/engrama/container.py`. O container conhece as classes concretas de `infrastructure` e liga os casos de uso aos `entrypoints`. Solto na raiz do pacote, ele não pertence a nenhuma camada, e o contrato de camadas do import-linter não consegue expressá-lo sem abrir uma exceção.

## Decisão

`engrama.bootstrap` (`settings.py`, `container.py`, `main.py`) é a camada mais externa. O contrato de camadas em `pyproject.toml` fica `bootstrap` > `entrypoints | infrastructure` > `application` > `domain`. O script `engrama` aponta para `engrama.bootstrap.main:main`.

## Alternativas consideradas

- `container.py` na raiz com `ignore_imports` no contrato: funciona, mas enfraquece justamente a regra que o plano quer garantir.
- Container dentro de `infrastructure`: inverteria a dependência, porque a infraestrutura passaria a conhecer os entrypoints.

## Consequências

- Só `bootstrap` importa classes concretas de mais de uma camada. Um handler continua sem conhecer o adapter do Neo4j.
- Quem procurar `container.py` na raiz pelo plano não o encontra; `docs/arquitetura.md` descreve o caminho real.
