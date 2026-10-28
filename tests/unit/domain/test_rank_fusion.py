"""Fusao das duas metades da busca.

O que esta suite protege e a propriedade que justifica o RRF existir: aparecer
nas duas listas vale mais do que ser primeiro em uma so. Se isso quebrar, a
busca hibrida vira a busca por palavra com ruido vetorial em cima.
"""

import pytest

from engrama.domain.services import ReciprocalRankFusion


def test_lista_unica_sai_na_mesma_ordem():
    fused = ReciprocalRankFusion().fuse(["a", "b", "c"])

    assert [item.key for item in fused] == ["a", "b", "c"]


def test_estar_nas_duas_listas_vale_mais_que_ser_primeiro_em_uma():
    fusion = ReciprocalRankFusion()

    fused = fusion.fuse(["so-lexical", "nas-duas"], ["so-vetorial", "nas-duas"])

    assert fused[0].key == "nas-duas", "segundo lugar nas duas listas ganha de primeiro em uma"
    assert fused[0].found_by_all
    assert not fused[1].found_by_all


def test_guarda_a_posicao_em_cada_lista():
    fused = {item.key: item for item in ReciprocalRankFusion().fuse(["a", "b"], ["b"])}

    assert fused["a"].ranks == (1, None)
    assert fused["b"].ranks == (2, 1)


def test_chave_repetida_na_mesma_lista_conta_a_melhor_posicao():
    fusion = ReciprocalRankFusion(k=1)

    fused = fusion.fuse(["a", "a"])

    assert len(fused) == 1
    assert fused[0].ranks == (1,)
    assert fused[0].score == pytest.approx(0.5)


def test_k_menor_da_mais_peso_ao_primeiro_lugar():
    """O `k` e o unico parametro do metodo, e isto e o que ele controla.

    Com as listas fundas o bastante, `k=60` prefere o pedaco que as duas
    buscas acharam em 4o lugar, e `k=1` prefere o que uma achou em 1o.
    """
    lexical = ["so-lexical", "x1", "x2", "nas-duas"]
    vetorial = ["so-vetorial", "y1", "y2", "nas-duas"]

    com_k_alto = ReciprocalRankFusion(k=60).fuse(lexical, vetorial)
    com_k_baixo = ReciprocalRankFusion(k=1).fuse(lexical, vetorial)

    assert com_k_alto[0].key == "nas-duas", "com k=60 vale mais aparecer nas duas"
    assert com_k_baixo[0].key == "so-lexical", "com k=1 o primeiro lugar domina"


def test_empate_e_desfeito_pela_chave():
    """Sem isso a ordem dependeria da iteracao de um dicionario, e o mesmo
    teste passaria ou falharia conforme a ordem de insercao."""
    fused = ReciprocalRankFusion().fuse(["b", "a"], ["a", "b"])

    assert [item.key for item in fused] == ["a", "b"]
    assert fused[0].score == pytest.approx(fused[1].score)


def test_sem_lista_nenhuma_nao_devolve_nada():
    assert ReciprocalRankFusion().fuse() == ()
    assert ReciprocalRankFusion().fuse([], []) == ()


def test_k_invalido_e_recusado_na_construcao():
    with pytest.raises(ValueError, match="k do RRF"):
        ReciprocalRankFusion(k=0)
