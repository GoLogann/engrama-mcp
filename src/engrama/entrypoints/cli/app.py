from collections.abc import Callable
from importlib.metadata import version as package_version
from typing import Annotated

import typer

from engrama.application.dto.ingestion import IngestionReport
from engrama.application.dto.structure_check import StructureCheckReport
from engrama.application.use_cases.build_structural_graph import BuildStructuralGraph
from engrama.application.use_cases.check_structure import CheckStructureAgainstGroundTruth


def build_cli(
    build_structural_graph: Callable[[], BuildStructuralGraph],
    check_structure: Callable[[], CheckStructureAgainstGroundTruth],
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
    def ingest(
        repo: Annotated[
            list[str] | None, typer.Option(help="Só estes repos (padrão: todos do catálogo).")
        ] = None,
    ) -> None:
        """Extrai os repos do catálogo e grava a camada de estrutura no Neo4j."""
        _print_ingestion(build_structural_graph().execute(only=repo or ()))

    @app.command("check-structure")
    def check_structure_command() -> None:
        """Portão 1: compara o grafo com eval/structure_groundtruth.yaml."""
        report = check_structure().execute()
        _print_check(report)
        if not report.passed:
            raise typer.Exit(code=1)

    return app


def _print_ingestion(report: IngestionReport) -> None:
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
    if report.diagnostics:
        typer.echo(f"\nDiagnósticos ({len(report.diagnostics)}):")
        for diagnostic in report.diagnostics:
            typer.echo(f"  {diagnostic}")


def _print_check(report: StructureCheckReport) -> None:
    typer.echo(
        f"Rotas: {report.route_coverage:.0%} de {report.expected_routes} | "
        f"Chamadas: {report.call_coverage:.0%} de {report.expected_calls}"
    )
    sections = (
        ("Rotas faltando", report.missing_routes),
        ("Rotas a mais", report.unexpected_routes),
        ("Chamadas faltando", report.missing_calls),
        ("Chamadas a mais", report.unexpected_calls),
    )
    for title, facts in sections:
        if facts:
            typer.echo(f"\n{title} ({len(facts)}):")
            for fact in facts:
                typer.echo(f"  {fact}")
    typer.echo("\nPortão 1: " + ("aprovado" if report.passed else "reprovado"))
