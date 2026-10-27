# ADR 0009 — Vigência das arestas no Neo4j, nós permanentes e ingestão parcial

- **Status:** aceita
- **Data:** 27/10/2026

## Contexto

O modelo bitemporal do doc de fundamentação pede `valid_from`, `valid_to` e `ingested_at`, e diz que o que deixa de valer é invalidado, não apagado. A extração é determinística e roda de novo a cada ingestão, então é preciso distinguir "o fato continua" de "o fato sumiu" sem perder o histórico. O plano não dizia como fazer isso no grafo, e a revisão das Fases 0 e 1 achou dois defeitos nessa parte (`ingested_at` sobrescrito e ingestão parcial que fechava `CALLS` válidas).

## Decisão

1. **Uma aresta aberta por fato.** Cada aresta tem `open` (booleano) e `valid_to`. A escrita usa `MERGE (s)-[r:TIPO {open: true}]->(t)`, então existe no máximo uma aresta aberta por (tipo, origem, destino).
2. **`valid_from` e `ingested_at` só na criação** (`ON CREATE`). Reingerir o mesmo fato não os muda: dizem quando ele passou a valer e quando o grafo soube dele.
3. **Dono e rodada.** Toda aresta de extração tem o repo que a originou (`owner`) e o `run_id` da rodada. No fim de uma rodada, a aresta aberta de um dono regravado que não foi reencontrada ganha `open = false` e `valid_to`.
4. **`CALLS` sem destino fecha.** Uma `CALLS` cujo `Endpoint` não tem mais `EXPOSES` aberta é fechada, mesmo que o dono dela (o cliente) não tenha sido regravado. Essa consulta vale para o banco inteiro.
5. **Nós nunca fecham.** Só arestas. Um endpoint que sumiu continua como nó, sem `EXPOSES` aberta.
6. **Ingestão parcial traz os relacionados.** `Catalog.with_related` inclui, além dos repos pedidos, os clientes deles e todos os servidores de cada repo que entrou. Uma `CALLS` só existe se cliente e servidor entram na mesma rodada.

## Alternativas consideradas

- Apagar e recriar o grafo a cada ingestão: perde o histórico e não responde "o que valia em tal data".
- Fechar também os nós sem arestas abertas: possível depois, se as consultas ficarem complicadas; hoje acrescentaria uma regra a mais sem ganho medido.
- Ingestão parcial só dos repos pedidos, avisando o usuário: foi o que existiu até a revisão, e gravava um histórico falso sem erro nenhum.

## Consequências

- O MCP (Fase 4) responde "o que vale hoje" lendo só arestas abertas, e "o que valia em X" com `valid_from` e `valid_to`. Consulta que parte de nós sem olhar a aresta aberta devolve endpoints que já não existem.
- `engrama ingest --repo X` pode ingerir mais repos do que o pedido; a CLI lista os incluídos.
- Um repo que faz chamadas sem declarar `consumes` em `config/repos.yaml` não é relacionado a ninguém numa ingestão parcial; `engrama ingest` sem `--repo` sempre refaz tudo.
