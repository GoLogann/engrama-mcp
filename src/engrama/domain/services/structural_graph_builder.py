from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from engrama.domain.entities import (
    DataStore,
    DataStoreKind,
    Edge,
    EdgeKind,
    Endpoint,
    Issue,
    Module,
    Node,
    Project,
    Repo,
)
from engrama.domain.services.call_route_matcher import RouteMatch
from engrama.domain.value_objects import Evidence, NodeRef, Provenance, Validity
from engrama.domain.value_objects.code_facts import DataStoreUse, DeclaredRoute, IssueReference

ROOT_MODULE = "."


@dataclass(frozen=True, slots=True)
class StructuralGraph:
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]


def _ancestors(path: str) -> list[str]:
    """`app/api/v1` -> [`app/api/v1`, `app/api`, `app`]."""
    if path == ROOT_MODULE:
        return [ROOT_MODULE]
    pure = PurePosixPath(path)
    return [str(pure)] + [str(parent) for parent in pure.parents if str(parent) != "."]


class StructuralGraphBuilder:
    """Monta a camada de estrutura a partir dos fatos extraidos de um repo.

    Toda aresta sai com origem `extraction` e a evidencia de onde o fato foi
    visto. Arestas repetidas (dois pontos do mesmo modulo citando a mesma
    issue) viram uma aresta so, com todas as evidencias.
    """

    def repository(
        self,
        project: Project,
        repo: Repo,
        modules: Iterable[str],
        routes: Sequence[DeclaredRoute],
        datastores: Sequence[DataStoreUse],
        issues: Sequence[IssueReference],
        validity: Validity,
    ) -> StructuralGraph:
        nodes: dict[NodeRef, Node] = {project.ref: project, repo.ref: repo}
        edges: list[Edge] = [
            self._edge(
                EdgeKind.PART_OF, repo.ref, project.ref, [Evidence.in_document(repo.url)], validity
            )
        ]

        module_paths = (
            set(modules) | {route.module for route in routes} | {i.module for i in issues}
        )
        for path in sorted({a for m in module_paths for a in _ancestors(m)}):
            module = Module(repo.name, path)
            nodes[module.ref] = module
            parent = PurePosixPath(path).parent
            parent_ref = (
                repo.ref
                if path == ROOT_MODULE or str(parent) == "."
                else Module(repo.name, str(parent)).ref
            )
            directory = Evidence.in_code(repo.name, path, repo.commit)
            edges.append(
                self._edge(EdgeKind.PART_OF, module.ref, parent_ref, [directory], validity)
            )

        for route in routes:
            endpoint = Endpoint(route.repo, route.route, route.handler)
            nodes[endpoint.ref] = endpoint
            module_ref = Module(route.repo, route.module).ref
            edges.append(
                self._edge(EdgeKind.EXPOSES, module_ref, endpoint.ref, [route.evidence], validity)
            )

        for use in datastores:
            store = DataStore(use.repo, DataStoreKind(use.kind), use.name)
            nodes[store.ref] = store
            edges.append(
                self._edge(EdgeKind.STORES_IN, repo.ref, store.ref, use.evidence, validity)
            )

        grouped: dict[tuple[NodeRef, NodeRef], list[Evidence]] = defaultdict(list)
        for reference in issues:
            issue = Issue(reference.issue_repo, reference.number)
            nodes[issue.ref] = issue
            grouped[(Module(reference.repo, reference.module).ref, issue.ref)].append(
                reference.evidence
            )
        for (source, target), evidence in grouped.items():
            edges.append(self._edge(EdgeKind.REFERENCES_ISSUE, source, target, evidence, validity))

        return StructuralGraph(tuple(nodes.values()), tuple(edges))

    def calls(self, matches: Sequence[RouteMatch], validity: Validity) -> tuple[Edge, ...]:
        """CALLS do modulo cliente para o endpoint, com a evidencia dos dois lados:
        o ponto da chamada e a declaracao da rota."""
        grouped: dict[tuple[NodeRef, NodeRef], list[Evidence]] = defaultdict(list)
        for match in matches:
            source = Module(match.call.repo, match.call.module).ref
            target = Endpoint(match.route.repo, match.route.route).ref
            evidence = grouped[(source, target)]
            evidence.append(match.call.evidence)
            if match.route.evidence not in evidence:
                evidence.append(match.route.evidence)
        return tuple(
            self._edge(EdgeKind.CALLS, source, target, evidence, validity)
            for (source, target), evidence in grouped.items()
        )

    @staticmethod
    def _edge(
        kind: EdgeKind,
        source: NodeRef,
        target: NodeRef,
        evidence: Sequence[Evidence],
        validity: Validity,
    ) -> Edge:
        return Edge(kind, source, target, Provenance.extracted(*evidence), validity)
