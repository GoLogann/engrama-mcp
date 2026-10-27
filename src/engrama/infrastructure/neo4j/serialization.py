import json
from dataclasses import fields
from enum import Enum
from typing import Any

from engrama.domain.entities import Edge, Node
from engrama.domain.value_objects import Evidence, HttpRoute

# Conversao entre o dominio e as propriedades do Neo4j, que so aceitam
# escalares e listas de escalares.


def node_properties(node: Node) -> dict[str, Any]:
    properties: dict[str, Any] = {"key": node.key}
    for field in fields(node):  # type: ignore[arg-type]
        value = getattr(node, field.name)
        if isinstance(value, HttpRoute):
            properties["method"] = value.method.value
            properties["path"] = value.path
            properties["route"] = str(value)
        elif isinstance(value, Enum):
            properties[field.name] = value.value
        elif isinstance(value, tuple):
            properties[field.name] = [str(item) for item in value]
        else:
            properties[field.name] = value
    return properties


def evidence_json(evidence: tuple[Evidence, ...]) -> str:
    return json.dumps(
        [
            {k: v for k, v in (("repo", e.repo), ("path", e.path), ("line", e.line),
                               ("commit", e.commit), ("url", e.url)) if v is not None}
            for e in evidence
        ]
    )  # fmt: skip


def edge_properties(edge: Edge, owner: str, run_id: str) -> dict[str, Any]:
    return {
        "source": edge.provenance.source.value,
        "confidence": edge.provenance.confidence.value,
        "evidence": [str(e) for e in edge.provenance.evidence],
        "evidence_json": evidence_json(edge.provenance.evidence),
        "owner": owner,
        "run_id": run_id,
    }
