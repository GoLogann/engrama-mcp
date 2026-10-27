from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from neo4j import Driver, ManagedTransaction

from engrama.application.ports.graph import GraphWriter
from engrama.domain.services import StructuralGraph
from engrama.infrastructure.neo4j.serialization import edge_properties, node_properties

SCHEMA = Path(__file__).with_name("schema.cypher")

# Rotulos e tipos de aresta vem de enums do dominio, nunca de entrada externa,
# por isso podem ser interpolados na consulta (o Cypher nao os parametriza).
_UPSERT_NODES = "UNWIND $rows AS row MERGE (n:{label} {{key: row.key}}) SET n += row"
_UPSERT_EDGES = """
UNWIND $rows AS row
MATCH (s:{source} {{key: row.source}})
MATCH (t:{target} {{key: row.target}})
MERGE (s)-[r:{kind} {{open: true}}]->(t)
ON CREATE SET r.valid_from = row.valid_from, r.ingested_at = row.ingested_at
SET r += row.props
"""
# `valid_from` e `ingested_at` so entram na criacao: dizem quando o fato passou
# a valer e quando o grafo soube dele, e reingerir o mesmo fato nao muda isso.

# Fato de extracao que nao apareceu nesta rodada deixou de valer: ganha
# `valid_to` e fecha, mas continua no grafo (modelo bitemporal).
_RETIRE_STALE = """
MATCH ()-[r]->()
WHERE r.owner = $owner AND r.source = 'extraction' AND r.open AND r.run_id <> $run_id
SET r.open = false, r.valid_to = $at
"""
# A CALLS pertence ao cliente. Numa reingestao so da API, a rota pode sumir sem
# o cliente ser regravado: a chamada fica sem destino e tambem deixa de valer.
_CLOSE_ORPHAN_CALLS = """
MATCH ()-[c:CALLS {open: true}]->(e:Endpoint)
WHERE NOT EXISTS { MATCH ()-[:EXPOSES {open: true}]->(e) }
SET c.open = false, c.valid_to = $at
"""


class Neo4jGraphWriter(GraphWriter):
    def __init__(self, driver: Driver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    def ensure_schema(self) -> None:
        statements = [
            s.strip()
            for s in SCHEMA.read_text().split(";")
            if s.strip() and not all(line.startswith("//") for line in s.strip().splitlines())
        ]
        with self._driver.session(database=self._database) as session:
            for statement in statements:
                session.run(statement).consume()

    def write(self, graphs: Mapping[str, StructuralGraph], run_id: str, at: datetime) -> None:
        with self._driver.session(database=self._database) as session:
            session.execute_write(self._write, graphs, run_id, at)

    @staticmethod
    def _write(
        tx: ManagedTransaction, graphs: Mapping[str, StructuralGraph], run_id: str, at: datetime
    ) -> None:
        nodes = defaultdict(dict)
        for graph in graphs.values():
            for node in graph.nodes:
                nodes[node.node_kind.value][node.key] = node_properties(node)
        for label, rows in nodes.items():
            tx.run(_UPSERT_NODES.format(label=label), rows=list(rows.values())).consume()

        edges = defaultdict(list)
        for owner, graph in graphs.items():
            for edge in graph.edges:
                edges[(edge.kind.value, edge.source.kind.value, edge.target.kind.value)].append(
                    {
                        "source": edge.source.key,
                        "target": edge.target.key,
                        "valid_from": edge.validity.valid_from,
                        "ingested_at": edge.validity.ingested_at,
                        "props": edge_properties(edge, owner, run_id),
                    }
                )
        for (kind, source, target), rows in edges.items():
            query = _UPSERT_EDGES.format(kind=kind, source=source, target=target)
            tx.run(query, rows=rows).consume()

        for owner in graphs:
            tx.run(_RETIRE_STALE, owner=owner, run_id=run_id, at=at).consume()
        tx.run(_CLOSE_ORPHAN_CALLS, at=at).consume()
