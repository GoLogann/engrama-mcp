from pathlib import Path

import yaml

from engrama.application.dto.ingestion import Catalog, RepositorySpec
from engrama.application.ports.sources import RepositoryCatalog
from engrama.domain.entities import Project, Repo, Stack


class YamlRepositoryCatalog(RepositoryCatalog):
    """Le config/repos.yaml."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> Catalog:
        data = yaml.safe_load(self._path.read_text())
        projects = tuple(Project(p["slug"], p["name"]) for p in data["projects"])
        repos = tuple(
            RepositorySpec(
                repo=Repo(
                    name=r["name"],
                    project=r["project"],
                    url=r["url"],
                    commit=r["commit"],
                    stack=Stack(r["stack"]),
                ),
                consumes=tuple(r.get("consumes", ())),
                base_path=r.get("base_path", ""),
            )
            for r in data["repos"]
        )
        return Catalog(projects=projects, repos=repos)
