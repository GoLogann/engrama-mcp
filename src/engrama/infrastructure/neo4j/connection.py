from collections.abc import Iterator

from neo4j import Driver, GraphDatabase


def open_driver(uri: str, user: str, password: str) -> Iterator[Driver]:
    """Recurso do container: abre o driver no primeiro uso e fecha no shutdown."""
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        yield driver
    finally:
        driver.close()
