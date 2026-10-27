from pathlib import Path

from engrama.application.dto.structure_check import DataStoreFact
from engrama.infrastructure.config.yaml_ground_truth import YamlGroundTruthSource

GROUND_TRUTH = Path(__file__).parents[3] / "eval" / "structure_groundtruth.yaml"


def test_groundtruth_do_repositorio_tem_as_contagens_conferidas_a_mao():
    truth = YamlGroundTruthSource(GROUND_TRUTH).load()

    assert len(truth.routes) == 75  # 30 na phishforge-api, 45 na phishing-quest-api
    assert len(truth.calls) == 33  # 27 do frontend, 6 do app
    assert truth.datastores == {
        DataStoreFact("phishforge-api", "postgres", "phishforge"),
        DataStoreFact("phishforge-api", "qdrant", "phishing_articles"),
        DataStoreFact("phishing-quest-api", "postgres", "phishing_quest"),
    }
