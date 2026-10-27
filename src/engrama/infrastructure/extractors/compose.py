from pathlib import PurePosixPath

import yaml

from engrama.application.dto.ingestion import CodeFacts, RepositorySpec
from engrama.application.ports.sources import CodeExtractor, SourceTree
from engrama.domain.entities import DataStoreKind
from engrama.domain.value_objects import Evidence
from engrama.domain.value_objects.code_facts import DataStoreUse

_COMPOSE_FILES = ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")


def _scalar(node: yaml.Node | None) -> str | None:
    return node.value if isinstance(node, yaml.ScalarNode) else None


def _mapping(node: yaml.Node | None) -> dict[str, yaml.Node]:
    if not isinstance(node, yaml.MappingNode):
        return {}
    return {key.value: value for key, value in node.value}


def _environment(node: yaml.Node | None) -> dict[str, str]:
    """`environment:` aceita mapa ou lista `CHAVE=valor`."""
    if isinstance(node, yaml.SequenceNode):
        pairs = (str(item.value).split("=", 1) for item in node.value)
        return {pair[0]: pair[1] for pair in pairs if len(pair) == 2}
    return {key: str(value.value) for key, value in _mapping(node).items()}


class ComposeExtractor(CodeExtractor):
    """Bancos declarados no docker compose da raiz do repo.

    Postgres conta como banco quando o servico define `POSTGRES_DB` (um
    servico que so usa a imagem como cliente, para `pg_dump`, nao conta).
    As migrations Flyway entram como evidencia extra do Postgres.
    """

    def supports(self, spec: RepositorySpec) -> bool:
        return True

    def extract(self, tree: SourceTree, spec: RepositorySpec) -> CodeFacts:
        repo = spec.repo
        compose = next((p for p in tree.files(_COMPOSE_FILES) if "/" not in p), None)
        if compose is None:
            return CodeFacts()
        root = yaml.compose(tree.read(compose))
        migrations = sorted({str(PurePosixPath(p).parent) for p in tree.files((".sql",))})

        services = _mapping(root).get("services")
        stores: list[DataStoreUse] = []
        for key, service in services.value if isinstance(services, yaml.MappingNode) else ():
            name, fields = key.value, _mapping(service)
            image = _scalar(fields.get("image")) or ""
            line = key.start_mark.line + 1
            evidence = Evidence.in_code(repo.name, compose, repo.commit, line)
            database = _environment(fields.get("environment")).get("POSTGRES_DB")
            if image.startswith("postgres") and database:
                extra = tuple(Evidence.in_code(repo.name, path, repo.commit) for path in migrations)
                stores.append(
                    DataStoreUse(repo.name, DataStoreKind.POSTGRES, database, (evidence, *extra))
                )
            elif "qdrant/qdrant" in image:
                stores.append(DataStoreUse(repo.name, DataStoreKind.QDRANT, name, (evidence,)))
            elif image.startswith("redis"):
                stores.append(DataStoreUse(repo.name, DataStoreKind.REDIS, name, (evidence,)))
        return CodeFacts(datastores=tuple(stores))
