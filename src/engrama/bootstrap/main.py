from engrama.bootstrap.container import Container
from engrama.entrypoints.cli.app import build_cli


def main() -> None:
    container = Container()
    try:
        build_cli(
            build_structural_graph=container.build_structural_graph,
            check_structure=container.check_structure,
        )()
    finally:
        container.shutdown_resources()
