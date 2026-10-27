# ADR 0006 — `Episode.supersede` no lugar de `superseded_by`

- **Status:** aceita
- **Data:** 27/10/2026

## Contexto

O plano descrevia `episode.superseded_by(novo, at)`, devolvendo o par (antigo com `valid_to` fechado, novo ligado por `SUPERSEDES`). Um sucessor herda tipo e `about` do antigo, mas precisa de id, texto e autor próprios.

## Decisão

`Episode.supersede(successor_id=…, text=…, author=…, at=…, episode_type=None, about=None)` cria o sucessor a partir do antigo e devolve `(antigo_encerrado, sucessor)`. O antigo é recusado (`EpisodeAlreadySuperseded`) se já foi encerrado, e o sucessor guarda `supersedes` com o id do antigo.

## Alternativas consideradas

- `superseded_by(novo, at)`: obrigaria quem chama a montar o sucessor com `supersedes` à mão, e o domínio teria de validar que ele aponta para o episódio certo.

## Consequências

- A garantia é a mesma: um episódio nunca é editado, e o histórico é linear. Só muda quem constrói o sucessor.
