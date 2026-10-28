from pathlib import Path

from engrama.infrastructure.config.yaml_golden_questions import YamlGoldenQuestions

ROOT = Path(__file__).parents[3]


def test_le_as_perguntas_do_arquivo_da_poc():
    questions = YamlGoldenQuestions(ROOT / "eval" / "golden_questions.yaml").load()

    assert len(questions) == 40
    assert all(question.sources for question in questions)
    assert all(question.must_contain for question in questions)
    assert {question.audience for question in questions} == {"tecnico", "nao_tecnico"}


def test_le_o_formato_minimo(tmp_path):
    path = tmp_path / "q.yaml"
    path.write_text(
        "perguntas:\n"
        "  - id: n01\n"
        "    publico: nao_tecnico\n"
        "    camada: documentacao\n"
        "    pergunta: O que e?\n"
        "    deve_conter: [uma coisa]\n"
        "    fontes: [api/README.md:3]\n"
    )

    questions = YamlGoldenQuestions(path).load()

    assert questions[0].id == "n01"
    assert questions[0].layer == "documentacao"
    assert questions[0].sources == ("api/README.md:3",)
