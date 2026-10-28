from pathlib import Path

import yaml

from engrama.application.dto.evaluation import GoldenQuestion
from engrama.application.ports.knowledge import GoldenQuestionSource


class YamlGoldenQuestions(GoldenQuestionSource):
    """Le eval/golden_questions.yaml (formato descrito no proprio arquivo)."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> tuple[GoldenQuestion, ...]:
        data = yaml.safe_load(self._path.read_text())
        return tuple(
            GoldenQuestion(
                id=item["id"],
                audience=item["publico"],
                layer=item["camada"],
                question=item["pergunta"],
                sources=tuple(item["fontes"]),
                must_contain=tuple(item.get("deve_conter", ())),
            )
            for item in data["perguntas"]
        )
