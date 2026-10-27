"""Guarda as perguntas de ouro (eval/golden_questions.yaml).

Confere o formato e se cada fonte citada existe, com a linha dentro do arquivo.
Se a linha *prova* a resposta, so uma pessoa diz: isso foi revisado a mao (ver
CONVERSATIONS.md). O teste pega o erro mecanico: arquivo renomeado, linha que
deixou de existir depois de trocar o commit fixado.

Fontes dos repos do LABit saem de `.cache/repos` (criado por `engrama ingest`);
sem o clone, o teste daquele repo e pulado.
"""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[3]
QUESTIONS = yaml.safe_load((ROOT / "eval" / "golden_questions.yaml").read_text())["perguntas"]
LABIT_REPOS = {"phishforge-api", "phishforge-frontend", "phishing-quest-api", "phishing_quest"}
LAYERS = {"estrutura", "documentacao", "experiencia"}


def test_sao_40_perguntas_metade_tecnica():
    audiences = [q["publico"] for q in QUESTIONS]

    assert len(QUESTIONS) == 40
    assert audiences.count("tecnico") == 20
    assert audiences.count("nao_tecnico") == 20
    assert len({q["id"] for q in QUESTIONS}) == 40


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda q: q["id"])
def test_pergunta_tem_o_que_a_correcao_precisa(question):
    assert question["pergunta"].endswith("?")
    assert question["camada"] in LAYERS
    assert question["deve_conter"], "sem criterio de acerto"
    assert question["fontes"], "sem fonte"


SOURCES = [(q["id"], source) for q in QUESTIONS for source in q["fontes"]]


@pytest.mark.parametrize(("question_id", "source"), SOURCES, ids=[f"{q}:{s}" for q, s in SOURCES])
def test_fonte_existe_e_a_linha_esta_no_arquivo(question_id, source):
    path, _, line = source.partition(":")
    repo = path.split("/", 1)[0]
    if repo in LABIT_REPOS:
        if not (ROOT / ".cache" / "repos" / repo).is_dir():
            pytest.skip(f"clone de {repo} ausente; rode `engrama ingest`")
        file = ROOT / ".cache" / "repos" / path
    else:
        file = ROOT / path

    assert file.is_file(), f"{question_id}: {source} nao existe"
    if line:
        assert 1 <= int(line) <= len(file.read_text(errors="replace").splitlines()), (
            f"{question_id}: {source} esta fora do arquivo"
        )
