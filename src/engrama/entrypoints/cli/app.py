from collections.abc import Callable
from importlib.metadata import version as package_version
from typing import Annotated

import typer

from engrama.application.dto.documentation import IndexingReport
from engrama.application.dto.evaluation import SourceRecallReport
from engrama.application.dto.ingestion import IngestionReport
from engrama.application.dto.knowledge import ChunkHit
from engrama.application.dto.structure_check import StructureCheckReport
from engrama.application.use_cases.build_structural_graph import BuildStructuralGraph
from engrama.application.use_cases.check_structure import CheckStructureAgainstGroundTruth
from engrama.application.use_cases.index_documents import IndexDocuments
from engrama.application.use_cases.measure_source_recall import MeasureSourceRecall
from engrama.application.use_cases.search_knowledge import SearchKnowledge
from engrama.domain.errors import UnknownRepository

REPO_OPTION = typer.Option(help="Só estes repos (padrão: todos do catálogo).")


def build_cli(
    build_structural_graph: Callable[[], BuildStructuralGraph],
    check_structure: Callable[[], CheckStructureAgainstGroundTruth],
    index_documents: Callable[[], IndexDocuments],
    search_knowledge: Callable[[], SearchKnowledge],
    measure_source_recall: Callable[[], MeasureSourceRecall],
) -> typer.Typer:
    """Monta a CLI. Os comandos recebem fabricas dos casos de uso, para que
    nada (nem a conexao com o Neo4j) seja criado so para mostrar o --help."""
    app = typer.Typer(
        help="engrama: cérebro de conhecimento em grafo dos projetos do LABit-UFPA.",
        no_args_is_help=True,
    )

    @app.command()
    def version() -> None:
        """Mostra a versão instalada."""
        typer.echo(package_version("engrama-mcp"))

    @app.command()
    def ingest(repo: Annotated[list[str] | None, REPO_OPTION] = None) -> None:
        """Extrai os repos do catálogo e grava a camada de estrutura no Neo4j."""
        report = _run(lambda: build_structural_graph().execute(only=repo or ()))
        _print_ingestion(report)

    @app.command("check-structure")
    def check_structure_command() -> None:
        """Portão 1: compara o grafo com eval/structure_groundtruth.yaml."""
        report = check_structure().execute()
        _print_check(report)
        if not report.passed:
            raise typer.Exit(code=1)

    @app.command("index-docs")
    def index_docs(repo: Annotated[list[str] | None, REPO_OPTION] = None) -> None:
        """Lê os documentos dos repos e grava a camada de documentação no Neo4j."""
        report = _run(lambda: index_documents().execute(only=repo or ()))
        _print_indexing(report)

    @app.command()
    def search(
        query: Annotated[str, typer.Argument(help="O que procurar nos documentos.")],
        limit: Annotated[int, typer.Option(help="Quantos pedaços mostrar.")] = 5,
    ) -> None:
        """Busca na camada de documentação e mostra os pedaços com a fonte."""
        hits = search_knowledge().execute(query, limit)
        if not hits:
            typer.echo("Nada encontrado. Os documentos já foram indexados (`engrama index-docs`)?")
            raise typer.Exit(code=1)
        _print_hits(hits)

    @app.command("check-sources")
    def check_sources(
        limit: Annotated[int, typer.Option(help="Tamanho da lista de resultados (k).")] = 10,
    ) -> None:
        """Mede se a busca acha a fonte que cada pergunta de ouro espera."""
        _print_recall(measure_source_recall().execute(limit))

    return app


def _run[T](action: Callable[[], T]) -> T:
    try:
        return action()
    except UnknownRepository as error:
        typer.echo(f"Erro: {error}", err=True)
        raise typer.Exit(code=2) from error


def _print_diagnostics(diagnostics: tuple[str, ...]) -> None:
    if diagnostics:
        typer.echo(f"\nDiagnósticos ({len(diagnostics)}):")
        for diagnostic in diagnostics:
            typer.echo(f"  {diagnostic}")


def _print_ingestion(report: IngestionReport) -> None:
    if report.related:
        typer.echo(
            f"Incluídos por serem clientes ou servidores dos pedidos: {', '.join(report.related)}\n"
        )
    for repo in report.repos:
        typer.echo(
            f"{repo.name}@{repo.commit[:7]}: {repo.modules} módulos, {repo.routes} rotas, "
            f"{repo.calls} chamadas, {repo.datastores} bancos, {repo.issues} citações de issue"
        )
    links = report.links
    typer.echo(
        f"\nChamadas casadas: {len(links.matches)} | sem rota: {len(links.unmatched_calls)} | "
        f"ambíguas: {len(links.ambiguous_calls)} | rotas sem cliente: "
        f"{len(links.routes_without_callers)}"
    )
    for call in links.unmatched_calls:
        typer.echo(f"  sem rota: {call.route} em {call.evidence}")
    for call, candidates in links.ambiguous_calls:
        options = ", ".join(c.repo for c in candidates)
        typer.echo(f"  ambígua: {call.route} em {call.evidence} ({options})")
    _print_diagnostics(report.diagnostics)


def _print_indexing(report: IndexingReport) -> None:
    for repo in report.repos:
        typer.echo(
            f"{repo.repo}: {repo.documents} documentos, {repo.decisions} decisões, "
            f"{repo.chunks} pedaços, {repo.endpoints_documented} endpoints documentados, "
            f"{repo.redactions} valores mascarados"
        )
    typer.echo(
        f"\nEndpoints conhecidos no grafo: {report.known_endpoints} | rotas citadas sem "
        f"endpoint: {len(report.unmatched)} | ambíguas: {len(report.ambiguous)}"
    )
    for mention in report.unmatched:
        typer.echo(f"  sem endpoint: {mention.route} em {mention.evidence}")
    for mention in report.ambiguous:
        typer.echo(f"  ambígua: {mention.route} em {mention.evidence}")
    if not report.known_endpoints:
        typer.echo(
            "Nenhum endpoint no grafo: rode `engrama ingest` para que uma rota citada num "
            "documento possa ser ligada ao endpoint que ela descreve."
        )
    _print_diagnostics(report.diagnostics)


def _print_hits(hits: list[ChunkHit]) -> None:
    for position, hit in enumerate(hits, start=1):
        title = f"{hit.document_title} — {hit.heading}" if hit.heading else hit.document_title
        typer.echo(f"{position}. {hit.source} ({hit.score:.2f}) {title}")
        for line in hit.text.strip().splitlines()[:3]:
            typer.echo(f"     {line[:96]}")
        typer.echo("")


def _print_recall(report: SourceRecallReport) -> None:
    typer.echo(
        f"Fontes de documento procuradas: {len(report.lookups)} de {report.questions} perguntas "
        f"(k={report.limit}) | fora do índice, por serem código: {len(report.skipped)}"
    )
    typer.echo(
        f"Arquivo certo na lista: {report.found}/{len(report.lookups)} "
        f"({report.file_recall:.0%}) | pedaço que cobre a linha citada: "
        f"{report.line_recall:.0%}"
    )
    if report.misses:
        typer.echo(f"\nNão encontradas ({len(report.misses)}):")
        for miss in report.misses:
            typer.echo(f"  {miss.question_id}: {miss.source}")
    found = [lookup for lookup in report.lookups if lookup.found]
    if found:
        typer.echo("\nPosição em que o arquivo esperado apareceu:")
        for lookup in found:
            mark = (
                ""
                if lookup.line is None
                else (" linha coberta" if lookup.covered else " linha fora do pedaço")
            )
            typer.echo(f"  {lookup.question_id}: {lookup.source} em {lookup.rank}º{mark}")


def _print_check(report: StructureCheckReport) -> None:
    typer.echo(
        f"Rotas: {report.route_coverage:.0%} de {report.expected_routes} | "
        f"Chamadas: {report.call_coverage:.0%} de {report.expected_calls} | "
        f"Bancos: {report.datastore_coverage:.0%} de {report.expected_datastores}"
    )
    sections = (
        ("Rotas faltando", report.missing_routes),
        ("Rotas a mais", report.unexpected_routes),
        ("Chamadas faltando", report.missing_calls),
        ("Chamadas a mais", report.unexpected_calls),
        ("Bancos faltando", report.missing_datastores),
        ("Bancos a mais", report.unexpected_datastores),
    )
    for title, facts in sections:
        if facts:
            typer.echo(f"\n{title} ({len(facts)}):")
            for fact in facts:
                typer.echo(f"  {fact}")
    typer.echo("\nPortão 1: " + ("aprovado" if report.passed else "reprovado"))
