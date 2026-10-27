# ADR 0007 — Portas e casos de uso da ingestão além do plano

- **Status:** aceita
- **Data:** 27/10/2026

## Contexto

O plano listava as portas `SourceRepository`, `CodeExtractor`, `GraphWriter`, `GraphReader`, `SecretScanner` e `Clock`, e os casos de uso `IngestRepository`, `LinkCallsToRoutes` e `CheckStructureAgainstGroundTruth`. Implementar o Portão 1 pediu mais.

## Decisão

Portas novas (em `application/ports/`):
- `RepositoryCatalog`: de onde vêm os repos e os commits fixados (hoje `config/repos.yaml`).
- `SourceTree`: arquivos de um repo num commit, já com a política de segredos. Separa "obter o repo" (`SourceRepository`) de "ler arquivos com segurança".
- `StructureReader` e `GroundTruthSource`: leitura mínima do grafo e do groundtruth para o Portão 1. O `GraphReader` das tools do MCP continua para a Fase 4.

Caso de uso novo: `BuildStructuralGraph`, que orquestra a ingestão em duas passadas (extrair todos os repos, depois casar chamadas com rotas), porque o cliente e a API estão em repos diferentes.

## Alternativas consideradas

- Fazer o `check-structure` ler o Neo4j direto: o caso de uso passaria a depender do driver.

## Consequências

- Cada porta nova tem um fake em `tests/fakes/` e, quando há adapter real, uma suíte de contrato.
