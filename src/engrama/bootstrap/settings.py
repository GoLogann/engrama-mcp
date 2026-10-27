from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracao lida do ambiente e do `.env`.

    Fica no bootstrap porque so a raiz de composicao a consome: os adapters
    recebem os valores ja resolvidos pelo construtor.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("")

    llm_model: str = Field(default="claude-opus-5-5", validation_alias="ENGRAMA_LLM_MODEL")
    cache_dir: Path = Field(default=Path(".cache"), validation_alias="ENGRAMA_CACHE_DIR")
    repos_config: Path = Field(
        default=Path("config/repos.yaml"), validation_alias="ENGRAMA_REPOS_CONFIG"
    )
    ground_truth_path: Path = Field(
        default=Path("eval/structure_groundtruth.yaml"), validation_alias="ENGRAMA_GROUND_TRUTH"
    )
