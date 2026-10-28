from dependency_injector import containers, providers

from engrama.application.use_cases.build_structural_graph import BuildStructuralGraph
from engrama.application.use_cases.check_structure import CheckStructureAgainstGroundTruth
from engrama.application.use_cases.explain_connection import ExplainConnection
from engrama.application.use_cases.find_usages import AnalyzeImpact, FindUsages
from engrama.application.use_cases.get_project_overview import FindNode, GetProjectOverview
from engrama.application.use_cases.index_documents import IndexDocuments
from engrama.application.use_cases.ingest_repository import IngestRepository
from engrama.application.use_cases.link_calls_to_routes import LinkCallsToRoutes
from engrama.application.use_cases.measure_source_recall import MeasureSourceRecall
from engrama.application.use_cases.read_repository_documents import ReadRepositoryDocuments
from engrama.application.use_cases.resolve_node import ResolveNode
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
from engrama.infrastructure.embeddings.voyage_embedder import VoyageEmbedder
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
from engrama.infrastructure.neo4j.graph_reader import Neo4jGraphReader
from engrama.infrastructure.neo4j.graph_writer import Neo4jGraphWriter
from engrama.infrastructure.neo4j.knowledge_index import Neo4jKnowledgeIndex
from engrama.infrastructure.neo4j.structure_reader import Neo4jStructureReader
from engrama.infrastructure.neo4j.vector_store import Neo4jVectorStore
from engrama.infrastructure.security.secret_scanner import RegexSecretScanner
from engrama.infrastructure.system.clock import SystemClock


def embedder_or_none(api_key: str, model: str, dimensions: int) -> VoyageEmbedder | None:
    """O embedder, ou `None` quando nao ha chave configurada.

    Sem chave o projeto continua rodando com a reserva por palavra (ADR
    0011), que acha menos fontes. Quem decide isso e a raiz de composicao, e
    nao o adapter: o `VoyageEmbedder` recusa chave vazia de proposito, para
    ninguem construir um embedder que nao embute.
    """
    return VoyageEmbedder(api_key, model, dimensions) if api_key else None


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

    embedder = providers.Singleton(
        embedder_or_none,
        settings.provided.voyage_api_key.get_secret_value.call(),
        settings.provided.embedding_model,
        settings.provided.embedding_dimensions,
    )

    graph_writer = providers.Singleton(Neo4jGraphWriter, neo4j_driver)
    # Leitura separada da escrita: um handler de tool recebe graph_reader e
    # nao tem como escrever no grafo nem por engano (ISP + DIP).
    graph_reader = providers.Singleton(Neo4jGraphReader, neo4j_driver)
    structure_reader = providers.Singleton(Neo4jStructureReader, neo4j_driver)
    vector_store = providers.Singleton(Neo4jVectorStore, neo4j_driver)
    knowledge_index = providers.Singleton(Neo4jKnowledgeIndex, neo4j_driver, embedder)

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
        embedder=embedder,
        vectors=vector_store,
    )
    search_knowledge = providers.Factory(SearchKnowledge, knowledge_index)
    measure_source_recall = providers.Factory(
        MeasureSourceRecall, golden_questions, knowledge_index
    )
    # Tools de leitura do MCP (Fase 4). Nenhuma precisa de LLM nem de
    # embedding: sao consultas ao grafo com a evidencia de cada aresta.
    resolve_node = providers.Factory(ResolveNode, graph_reader)
    find_node = providers.Factory(FindNode, graph_reader)
    find_usages = providers.Factory(FindUsages, graph_reader, resolve_node)
    analyze_impact = providers.Factory(AnalyzeImpact, graph_reader, resolve_node)
    explain_connection = providers.Factory(ExplainConnection, graph_reader, resolve_node)
    project_overview = providers.Factory(GetProjectOverview, graph_reader)
