# ADR 0004 — Ontologia: nó `Issue`, origens por aresta e evidência

- **Status:** aceita para as Fases 0 e 1; a tabela de origens volta a ser revista nas Fases 2 e 3
- **Data:** 27/10/2026

## Contexto

O doc de fundamentação lista a aresta `REFERENCES_ISSUE` sem dizer para que nó ela aponta, e não fixa quem pode criar cada tipo de aresta. O princípio 1 só diz que o LLM não cria aresta estrutural.

## Decisão

- Criar o nó `Issue` (chave `repo#número`), alvo de `REFERENCES_ISSUE`.
- `Module` é um diretório, não um arquivo; o arquivo e a linha ficam na evidência.
- Codificar em `RULES` (`domain/entities/edge.py`) os pares de nós e as origens permitidas de cada aresta. As quatro arestas estruturais (`EXPOSES`, `CALLS`, `STORES_IN`, `PART_OF`) só aceitam `extraction`. `DOCUMENTED_IN` aceita extração, documento e LLM; `MENTIONS_CONCEPT`, documento, LLM e pessoa; `REFERENCES_ISSUE`, extração e pessoa; `ABOUT`, `AUTHORED_BY` e `SUPERSEDES`, pessoa e documento.
- Toda aresta exige ao menos uma `Evidence`, **exceto** as que partem de um `Episode`, cujo autor e data são a prova. Um `Episode` só nasce de pessoa ou documento.

## Alternativas consideradas

- Deixar `REFERENCES_ISSUE` sem alvo e guardar o número numa propriedade: perderia a navegação "quem cita esta issue".
- Aceitar "pessoa sem evidência" em qualquer aresta, como estava até a revisão das Fases 0 e 1: permitia criar uma aresta que ninguém consegue conferir.

## Consequências

- As origens de `DOCUMENTED_IN`, `MENTIONS_CONCEPT` e `ABOUT` são interpretação do autor e precisam ser validadas quando as Fases 2 e 3 criarem essas arestas. Uma síntese gerada por LLM na reflexão semanal, por exemplo, não cabe hoje como `Episode`.

  *Revalidação de 28/10/2026:* `DOCUMENTED_IN` passou a existir de verdade (ADR 0010) e a regra se sustentou — as duas formas que a extração cria (o `README.md` da raiz documenta o repo; uma rota citada no texto documenta aquele endpoint) usam `extraction`, e as formas que exigiriam interpretação ficaram de fora à espera do LLM, exatamente como a origem `llm` previa. `MENTIONS_CONCEPT` e `ABOUT` continuam sem nenhuma aresta no grafo, então seguem como interpretação não validada; a dúvida sobre a síntese de reflexão permanece aberta para a Fase 3.
