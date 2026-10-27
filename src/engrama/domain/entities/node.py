from abc import ABC, abstractmethod
from typing import ClassVar

from engrama.domain.value_objects import NodeKind, NodeRef


class Node(ABC):
    """Base das entidades do grafo.

    Entidade tem identidade: dois nos sao o mesmo quando tem a mesma familia e
    a mesma chave natural, mesmo que outros atributos difiram (por exemplo, um
    resumo regenerado). As subclasses sao dataclasses com `eq=False` para
    herdar esta igualdade.
    """

    __slots__ = ()

    node_kind: ClassVar[NodeKind]

    @property
    @abstractmethod
    def key(self) -> str: ...

    @property
    def ref(self) -> NodeRef:
        return NodeRef(self.node_kind, self.key)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Node) and self.ref == other.ref

    def __hash__(self) -> int:
        return hash(self.ref)
