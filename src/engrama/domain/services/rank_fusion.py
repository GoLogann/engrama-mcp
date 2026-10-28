from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FusedRank:
    """Um item depois da fusao, com a posicao que ele teve em cada lista.

    `ranks` guarda a posicao (1-based) por lista, na ordem em que as listas
    foram passadas, e `None` onde o item nao apareceu. E o que permite dizer
    *por que* um pedaco subiu: achado pelas duas buscas ou so por uma.
    """

    key: str
    score: float
    ranks: tuple[int | None, ...]

    @property
    def found_by_all(self) -> bool:
        return all(rank is not None for rank in self.ranks)


@dataclass(frozen=True, slots=True)
class ReciprocalRankFusion:
    """Junta listas ordenadas usando so a posicao, nunca a pontuacao.

    A busca por palavra devolve pontuacao do Lucene e a vetorial, similaridade
    de cosseno. As duas escalas nao sao comparaveis: somar ou normalizar exige
    escolher um fator arbitrario que muda por consulta. O RRF troca a
    pontuacao pela posicao, que e comparavel por construcao: cada lista
    contribui `1 / (k + posicao)`.

    `k` amortece o peso das primeiras posicoes. Com `k` pequeno o primeiro
    lugar de uma lista domina a fusao; com `k` grande as posicoes se
    aproximam e vale mais aparecer nas duas listas. 60 e o valor do artigo
    que propos o metodo (Cormack et al., 2009) e o padrao da literatura.
    """

    k: int = 60

    def __post_init__(self) -> None:
        if self.k < 1:
            raise ValueError("k do RRF precisa ser >= 1")

    def fuse(self, *rankings: Sequence[str]) -> tuple[FusedRank, ...]:
        """Funde as listas e devolve os itens do melhor para o pior.

        Chave repetida dentro de uma lista conta uma vez, na melhor posicao.
        Empate e desfeito pela chave, para a ordem nao depender da ordem de
        iteracao de um dicionario.
        """
        positions: dict[str, list[int | None]] = {}
        for index, ranking in enumerate(rankings):
            for position, key in enumerate(ranking, start=1):
                slots = positions.setdefault(key, [None] * len(rankings))
                if slots[index] is None:
                    slots[index] = position

        fused = [
            FusedRank(
                key=key,
                score=sum(1 / (self.k + rank) for rank in ranks if rank is not None),
                ranks=tuple(ranks),
            )
            for key, ranks in positions.items()
        ]
        return tuple(sorted(fused, key=lambda item: (-item.score, item.key)))
