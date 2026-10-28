import json

from neo4j import Driver

from engrama.application.dto.consulta import (
    Connection,
    Direction,
    NodeSummary,
    ProjectOverview,
)
from engrama.application.ports.graph import GraphReader
from engrama.domain.value_objects import NodeKind, NodeRef

# Profundidade maxima aceita em `path`. O limite do Cypher nao pode ser
# parametro, entao vai interpolado — e por isso e validado como inteiro dentro
# desta faixa antes de entrar na consulta.
MAX_DEPTH = 10

# `path` de um `Endpoint` e o caminho da rota, nao de arquivo: usar como
# fonte produziria `repo//api/v1/rankings`. So estas familias tem arquivo.
_FILE = "CASE WHEN n:Module OR n:Doc OR n:Decision OR n:Chunk THEN n.path ELSE null END"

# O rotulo de um no depende da familia: um `Endpoint` se chama pela rota, um
# `Module` pelo caminho, um `Doc` pelo titulo. Em Cypher para a ordenacao
# acontecer no banco, antes do LIMIT.
_LABEL = """
CASE
  WHEN n:Endpoint  THEN n.route
  WHEN n:Module    THEN n.path
  WHEN n:DataStore THEN n.store_kind + ' ' + n.name
  WHEN n:Doc OR n:Decision THEN n.title
  WHEN n:Project OR n:Repo THEN n.name
  ELSE n.key
END
"""

# `Chunk` fica de fora: resolver um nome nao e buscar texto. Procurar "README"
# traria dezenas de pedacos e nenhum nome — isso e trabalho do
# `search_knowledge`, que busca no conteudo.
_FIND = f"""
MATCH (n)
WHERE NOT n:Chunk AND (
     toLower(n.key) CONTAINS $text
  OR toLower(coalesce(n.name, '')) CONTAINS $text
  OR toLower(coalesce(n.path, '')) CONTAINS $text
  OR toLower(coalesce(n.route, '')) CONTAINS $text
  OR toLower(coalesce(n.title, '')) CONTAINS $text
)
WITH n, ({_LABEL}) AS label
// Casamento exato primeiro, depois o rotulo mais curto: entre
// `GET /api/v1/items` e `GET /api/v1/items/{{id}}`, o pedido costuma ser o
// primeiro. A chave desempata, para a ordem nao variar entre rodadas.
ORDER BY toLower(label) <> $text, size(label), n.key
LIMIT $limit
RETURN labels(n)[0] AS kind, n.key AS key, label AS label,
       coalesce(n.repo, n.name, '') AS repo, ({_FILE}) AS path
"""

_NODE = f"""
MATCH (n) WHERE n.key = $key AND $kind IN labels(n)
RETURN labels(n)[0] AS kind, n.key AS key, ({_LABEL}) AS label,
       coalesce(n.repo, n.name, '') AS repo, ({_FILE}) AS path
"""

_SUMMARY = """
  labels(%(n)s)[0] AS %(p)s_kind, %(n)s.key AS %(p)s_key,
  CASE
    WHEN %(n)s:Endpoint  THEN %(n)s.route
    WHEN %(n)s:Module    THEN %(n)s.path
    WHEN %(n)s:DataStore THEN %(n)s.store_kind + ' ' + %(n)s.name
    WHEN %(n)s:Doc OR %(n)s:Decision THEN %(n)s.title
    WHEN %(n)s:Project OR %(n)s:Repo THEN %(n)s.name
    ELSE %(n)s.key
  END AS %(p)s_label,
  coalesce(%(n)s.repo, %(n)s.name, '') AS %(p)s_repo,
  CASE WHEN %(n)s:Module OR %(n)s:Doc OR %(n)s:Decision OR %(n)s:Chunk
       THEN %(n)s.path ELSE null END AS %(p)s_path
"""

_EDGE_COLUMNS = f"""
RETURN type(e) AS kind, e.evidence_json AS evidence, e.source AS source,
       e.confidence AS confidence, e.ingested_at AS ingested_at,
{_SUMMARY % {"n": "a", "p": "origin"}},
{_SUMMARY % {"n": "b", "p": "target"}}
ORDER BY kind, target_key, origin_key
"""

_EDGES_IN = f"""
MATCH (a)-[e {{open: true}}]->(b)
WHERE b.key = $key AND $kind IN labels(b)
{_EDGE_COLUMNS}
"""

_EDGES_OUT = f"""
MATCH (a)-[e {{open: true}}]->(b)
WHERE a.key = $key AND $kind IN labels(a)
{_EDGE_COLUMNS}
"""

_OVERVIEW = """
MATCH (p:Project) WHERE p.key = $project
OPTIONAL MATCH (r:Repo)-[:PART_OF {open: true}]->(p)
WITH p, collect(DISTINCT r) AS repos
WITH p, repos, [one IN repos | one.name] AS names
OPTIONAL MATCH (m:Module) WHERE m.repo IN names
WITH p, repos, names, count(DISTINCT m) AS modules
OPTIONAL MATCH (:Module)-[:EXPOSES {open: true}]->(e:Endpoint) WHERE e.repo IN names
WITH p, repos, names, modules, count(DISTINCT e) AS endpoints
OPTIONAL MATCH (d:DataStore) WHERE d.repo IN names
WITH p, repos, names, modules, endpoints, collect(DISTINCT d) AS stores
OPTIONAL MATCH (doc) WHERE (doc:Doc OR doc:Decision) AND doc.repo IN names
WITH p, repos, modules, endpoints, stores, collect(DISTINCT doc) AS docs
RETURN p.name AS project, modules AS modules, endpoints AS endpoints,
       [one IN repos | {key: one.key, label: one.name, repo: one.name}] AS repos,
       [one IN stores | {key: one.key, label: one.store_kind + ' ' + one.name,
                         repo: one.repo}] AS stores,
       size(docs) AS documents,
       [one IN docs WHERE one.path = 'README.md'
        | {key: one.key, label: one.title, repo: one.repo, path: one.path}] AS readmes
"""


class Neo4jGraphReader(GraphReader):
    """Leitura do grafo para as tools do MCP.

    So o que vale hoje: toda travessia filtra `open: true` (ADR 0009). Um
    endpoint que deixou de ser exposto continua no grafo e nao aparece aqui.
    """

    def __init__(self, driver: Driver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    def find(self, text: str, limit: int = 10) -> list[NodeSummary]:
        wanted = text.strip().casefold()
        if not wanted or limit < 1:
            return []
        rows = self._run(_FIND, text=wanted, limit=limit)
        return [self._summary(row) for row in rows]

    def node(self, ref: NodeRef) -> NodeSummary | None:
        rows = self._run(_NODE, key=ref.key, kind=ref.kind.value)
        return self._summary(rows[0]) if rows else None

    def edges(self, ref: NodeRef, direction: Direction) -> list[Connection]:
        queries = {
            Direction.IN: (_EDGES_IN,),
            Direction.OUT: (_EDGES_OUT,),
            Direction.BOTH: (_EDGES_IN, _EDGES_OUT),
        }[direction]
        found = []
        for query in queries:
            found += [
                self._connection(row) for row in self._run(query, key=ref.key, kind=ref.kind.value)
            ]
        return found

    def path(self, origin: NodeRef, target: NodeRef, max_depth: int = 6) -> list[Connection]:
        depth = max(1, min(int(max_depth), MAX_DEPTH))
        if origin == target:
            return []
        query = f"""
        MATCH (a) WHERE a.key = $origin_key AND $origin_kind IN labels(a)
        MATCH (b) WHERE b.key = $target_key AND $target_kind IN labels(b)
        MATCH caminho = shortestPath((a)-[*..{depth}]-(b))
        WHERE all(r IN relationships(caminho) WHERE r.open)
        UNWIND range(0, size(relationships(caminho)) - 1) AS passo
        // A ordem dos passos e a da travessia, que ignora o sentido; a origem
        // e o destino de cada passo sao os da aresta de verdade. Sem isso o
        // caminho afirmaria que o endpoint expoe o modulo.
        WITH relationships(caminho)[passo] AS e, passo
        WITH e, passo, startNode(e) AS a, endNode(e) AS b
        RETURN type(e) AS kind, e.evidence_json AS evidence, e.source AS source,
               e.confidence AS confidence, e.ingested_at AS ingested_at,
        {_SUMMARY % {"n": "a", "p": "origin"}},
        {_SUMMARY % {"n": "b", "p": "target"}}
        ORDER BY passo
        """
        rows = self._run(
            query,
            origin_key=origin.key,
            origin_kind=origin.kind.value,
            target_key=target.key,
            target_kind=target.kind.value,
        )
        return [self._connection(row) for row in rows]

    def overview(self, project: str) -> ProjectOverview | None:
        rows = self._run(_OVERVIEW, project=project)
        if not rows:
            return None
        row = rows[0]
        return ProjectOverview(
            project=project,
            repos=tuple(self._from_map(one, NodeKind.REPO) for one in row["repos"]),
            modules=row["modules"],
            endpoints=row["endpoints"],
            datastores=tuple(self._from_map(one, NodeKind.DATASTORE) for one in row["stores"]),
            documents=row["documents"],
            readmes=tuple(self._from_map(one, NodeKind.DOC) for one in row["readmes"]),
        )

    def _run(self, cypher: str, **parameters: object) -> list[dict]:
        records, _, _ = self._driver.execute_query(
            cypher, database_=self._database, routing_="r", **parameters
        )
        return [dict(row) for row in records]

    @staticmethod
    def _from_map(row: dict, kind: NodeKind) -> NodeSummary:
        repo = row.get("repo") or ""
        path = row.get("path")
        return NodeSummary(
            ref=NodeRef(kind, row["key"]),
            label=row["label"] or row["key"],
            repo=repo,
            source=f"{repo}/{path}" if repo and path else "",
        )

    @classmethod
    def _summary(cls, row: dict, prefix: str = "") -> NodeSummary:
        at = (lambda name: row[f"{prefix}{name}"]) if prefix else row.__getitem__
        repo = at("repo") or ""
        path = at("path")
        return NodeSummary(
            ref=NodeRef(NodeKind(at("kind")), at("key")),
            label=at("label") or at("key"),
            repo=repo,
            source=f"{repo}/{path}" if repo and path else "",
        )

    @classmethod
    def _connection(cls, row: dict) -> Connection:
        """A evidencia vem como JSON na aresta; aqui vira `repo/caminho:linha`,
        que e o formato das fontes das perguntas de ouro."""
        evidence = tuple(
            f"{item['repo']}/{item['path']}" + (f":{item['line']}" if item.get("line") else "")
            for item in json.loads(row["evidence"] or "[]")
        )
        ingested = row["ingested_at"]
        return Connection(
            origin=cls._summary(row, "origin_"),
            target=cls._summary(row, "target_"),
            kind=row["kind"],
            evidence=evidence,
            source=row["source"] or "",
            confidence=row["confidence"] or "",
            ingested_at=ingested.to_native() if ingested is not None else None,
        )
