# ADR 0003 — Extratores registrados no container, sem `ExtractorRegistry`

- **Status:** aceita
- **Data:** 27/10/2026

## Contexto

O plano descrevia uma stack nova como "um `CodeExtractor` registrado no `ExtractorRegistry`". Não existe classe com esse nome. `docs/arquitetura.md` dizia que existia.

## Decisão

Os extratores são uma lista no container (`providers.List` em `bootstrap/container.py`), injetada em `IngestRepository`. O caso de uso pergunta `extractor.supports(spec)` a cada um e junta os `CodeFacts` dos que se aplicam. Acrescentar uma stack é escrever o extrator e acrescentá-lo a essa lista; o pipeline não muda, que era o objetivo do aberto/fechado.

## Alternativas consideradas

- Uma classe `ExtractorRegistry` com `register()`: seria uma camada de indireção sem comportamento próprio.

## Consequências

- Reabrir se a ingestão precisar registrar extratores dinamicamente, por plugin, ou escolher entre dois que se aplicam ao mesmo repo.
