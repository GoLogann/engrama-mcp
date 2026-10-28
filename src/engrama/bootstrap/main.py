from engrama.bootstrap.container import Container
from engrama.entrypoints.cli.app import build_cli


def main() -> None:
    container = Container()
    try:
        build_cli(
            build_structural_graph=container.build_structural_graph,
            check_structure=container.check_structure,
            index_documents=container.index_documents,
            search_knowledge=container.search_knowledge,
            measure_source_recall=container.measure_source_recall,
        )()
    finally:
        container.shutdown_resources()
