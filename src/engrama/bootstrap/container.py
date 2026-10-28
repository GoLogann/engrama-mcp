from dependency_injector import containers, providers

from engrama.application.use_cases.build_structural_graph import BuildStructuralGraph
from engrama.application.use_cases.check_structure import CheckStructureAgainstGroundTruth
from engrama.application.use_cases.index_documents import IndexDocuments
from engrama.application.use_cases.ingest_repository import IngestRepository
from engrama.application.use_cases.link_calls_to_routes import LinkCallsToRoutes
from engrama.application.use_cases.measure_source_recall import MeasureSourceRecall
from engrama.application.use_cases.read_repository_documents import ReadRepositoryDocuments
from engrama.application.use_cases.search_knowledge import SearchKnowledge
from engrama.bootstrap.settings import Settings
from engrama.domain.services import (
    DocumentationGraphBuilder,
    DocumentChunker,
    RouteMentionMatcher,
    RouteNormalizer,
    StructuralGraphBuilder,
)
from engrama.infrastructure.config.yaml_catalog import YamlRepositoryCatalog
from engrama.infrastructure.config.yaml_golden_questions import YamlGoldenQuestions
from engrama.infrastructure.config.yaml_ground_truth import YamlGroundTruthSource
from engrama.infrastructure.documents import RepositoryDocumentExtractor
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
from engrama.infrastructure.neo4j.knowledge_index import Neo4jKnowledgeIndex
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
    mention_matcher = providers.Singleton(RouteMentionMatcher)
    chunker = providers.Singleton(DocumentChunker, settings.provided.chunk_max_chars)
    documentation_builder = providers.Singleton(DocumentationGraphBuilder, chunker)

    catalog = providers.Singleton(YamlRepositoryCatalog, settings.provided.repos_config)
    ground_truth = providers.Singleton(YamlGroundTruthSource, settings.provided.ground_truth_path)
    golden_questions = providers.Singleton(YamlGoldenQuestions, settings.provided.questions_path)
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
    document_extractor = providers.Singleton(RepositoryDocumentExtractor, route_normalizer)

    graph_writer = providers.Singleton(Neo4jGraphWriter, neo4j_driver)
    structure_reader = providers.Singleton(Neo4jStructureReader, neo4j_driver)
    knowledge_index = providers.Singleton(Neo4jKnowledgeIndex, neo4j_driver)

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

    read_documents = providers.Factory(
        ReadRepositoryDocuments, source_repository, document_extractor, secret_scanner
    )
    index_documents = providers.Factory(
        IndexDocuments,
        catalog=catalog,
        read=read_documents,
        matcher=mention_matcher,
        builder=documentation_builder,
        writer=graph_writer,
        structure=structure_reader,
        clock=clock,
    )
    search_knowledge = providers.Factory(SearchKnowledge, knowledge_index)
    measure_source_recall = providers.Factory(
        MeasureSourceRecall, golden_questions, knowledge_index
    )
