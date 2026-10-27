import json

from neo4j import Driver

from engrama.application.dto.structure_check import CallFact, DataStoreFact, RouteFact
from engrama.application.ports.graph import StructureReader
from engrama.domain.value_objects import HttpMethod, HttpRoute

_ROUTES = """
MATCH (:Module)-[r:EXPOSES {open: true}]->(e:Endpoint)
RETURN e.repo AS repo, e.route AS route, r.evidence_json AS evidence
"""
_CALLS = """
MATCH (m:Module)-[r:CALLS {open: true}]->(e:Endpoint)
RETURN m.repo AS caller, e.repo AS target, e.method AS method, e.path AS path,
       r.evidence_json AS evidence
"""


_DATASTORES = """
MATCH (:Repo)-[:STORES_IN {open: true}]->(d:DataStore)
RETURN d.repo AS repo, d.store_kind AS kind, d.name AS name
"""


class Neo4jStructureReader(StructureReader):
    def __init__(self, driver: Driver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    def routes(self) -> list[RouteFact]:
        records, _, _ = self._driver.execute_query(_ROUTES, database_=self._database)
        return [
            RouteFact(row["repo"], evidence["path"], evidence["line"], row["route"])
            for row in records
            for evidence in json.loads(row["evidence"])
        ]

    def datastores(self) -> list[DataStoreFact]:
        records, _, _ = self._driver.execute_query(_DATASTORES, database_=self._database)
        return [DataStoreFact(row["repo"], row["kind"], row["name"]) for row in records]

    def calls(self) -> list[CallFact]:
        """Uma CALLS carrega a evidencia dos dois lados; os pontos de chamada
        sao as evidencias do repo cliente."""
        records, _, _ = self._driver.execute_query(_CALLS, database_=self._database)
        facts = []
        for row in records:
            shape = HttpRoute(HttpMethod(row["method"]), row["path"]).shape
            for evidence in json.loads(row["evidence"]):
                if evidence.get("repo") == row["caller"]:
                    facts.append(
                        CallFact(
                            row["caller"], evidence["path"], evidence["line"], shape, row["target"]
                        )
                    )
        return facts
