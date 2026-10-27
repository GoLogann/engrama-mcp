from importlib.metadata import version as package_version

import typer


def build_cli() -> typer.Typer:
    """Monta a CLI. Os comandos recebem os casos de uso prontos do bootstrap."""
    app = typer.Typer(
        help="engrama: cérebro de conhecimento em grafo dos projetos do LABit-UFPA.",
        no_args_is_help=True,
    )

    @app.callback()
    def root() -> None:
        """Mantem os comandos como subcomandos mesmo enquanto ha poucos."""

    @app.command()
    def version() -> None:
        """Mostra a versao instalada."""
        typer.echo(package_version("engrama-mcp"))

    return app
