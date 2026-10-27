from dependency_injector import containers, providers

from engrama.application.use_cases.build_structural_graph import BuildStructuralGraph
from engrama.application.use_cases.check_structure import CheckStructureAgainstGroundTruth
from engrama.application.use_cases.ingest_repository import IngestRepository
from engrama.application.use_cases.link_calls_to_routes import LinkCallsToRoutes
from engrama.bootstrap.settings import Settings
from engrama.domain.services import RouteNormalizer, StructuralGraphBuilder
from engrama.infrastructure.config.yaml_catalog import YamlRepositoryCatalog
from engrama.infrastructure.config.yaml_ground_truth import YamlGroundTruthSource
from engrama.infrastructure.extractors import (
    ComposeExtractor,
    FastApiExtractor,
    FlutterExtractor,
    GinExtractor,
    IssueReferenceExtractor,
    ReactServiceExtractor,
)
from engrama.infrastructure.git.git_source_repository import GitSourceRepository
from engrama.infrastructure.neo4j.connection import open_driver
from engrama.infrastructure.neo4j.graph_writer import Neo4jGraphWriter
from engrama.infrastructure.neo4j.structure_reader import Neo4jStructureReader
from engrama.infrastructure.security.secret_scanner import RegexSecretScanner
from engrama.infrastructure.system.clock import SystemClock


class Container(containers.DeclarativeContainer):
    """Raiz de composicao: o unico lugar que conhece as classes concretas.

    Casos de uso recebem portas pelo construtor; aqui cada porta e ligada ao
    seu adapter. Trocar Neo4j, LLM ou embedder e mudar uma linha deste arquivo.
    """

    settings = providers.Singleton(Settings)

    neo4j_driver = providers.Resource(
        open_driver,
        settings.provided.neo4j_uri,
        settings.provided.neo4j_user,
        settings.provided.neo4j_password.get_secret_value.call(),
    )

    clock = providers.Singleton(SystemClock)
    secret_scanner = providers.Singleton(RegexSecretScanner)
    route_normalizer = providers.Singleton(RouteNormalizer)
    graph_builder = providers.Singleton(StructuralGraphBuilder)

    catalog = providers.Singleton(YamlRepositoryCatalog, settings.provided.repos_config)
    ground_truth = providers.Singleton(YamlGroundTruthSource, settings.provided.ground_truth_path)
    source_repository = providers.Singleton(
        GitSourceRepository, settings.provided.cache_dir, secret_scanner
    )

    # Uma stack nova entra aqui, sem mudar o pipeline (aberto/fechado).
    extractors = providers.List(
        providers.Singleton(FastApiExtractor, route_normalizer),
        providers.Singleton(GinExtractor, route_normalizer),
        providers.Singleton(ReactServiceExtractor, route_normalizer),
        providers.Singleton(FlutterExtractor, route_normalizer),
        providers.Singleton(ComposeExtractor),
        providers.Singleton(IssueReferenceExtractor, catalog.provided.load.call().repo_names),
    )

    graph_writer = providers.Singleton(Neo4jGraphWriter, neo4j_driver)
    structure_reader = providers.Singleton(Neo4jStructureReader, neo4j_driver)

    ingest_repository = providers.Factory(IngestRepository, source_repository, extractors)
    link_calls_to_routes = providers.Factory(LinkCallsToRoutes, graph_builder)
    build_structural_graph = providers.Factory(
        BuildStructuralGraph,
        catalog=catalog,
        ingest=ingest_repository,
        link=link_calls_to_routes,
        builder=graph_builder,
        writer=graph_writer,
        clock=clock,
    )
    check_structure = providers.Factory(
        CheckStructureAgainstGroundTruth, structure_reader, ground_truth
    )
