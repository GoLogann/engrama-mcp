from engrama.application.dto.consulta import NodeSummary, Resolution
from engrama.application.ports.graph import GraphReader

# Quantos candidatos olhar antes de decidir. Mais do que isto nao ajuda: se a
# resposta certa nao esta entre os dez primeiros, o texto era vago demais e a
# saida honesta e pedir precisao, nao varrer o grafo.
_CANDIDATES = 10


class ResolveNode:
    """Transforma o texto que a tool recebeu no no do grafo que ele nomeia.

    Casamento exato primeiro, candidato unico depois, e recusa quando ha mais
    de um — o mesmo criterio do `RouteMentionMatcher` (ADR 0010), pela mesma
    razao: escolher entre dois nos parecidos e adivinhar, e uma resposta
    errada com fonte convincente e pior que um pedido de precisao.
    """

    def __init__(self, reader: GraphReader) -> None:
        self._reader = reader

    def execute(self, text: str, limit: int = _CANDIDATES) -> Resolution:
        query = text.strip()
        if not query:
            return Resolution(query="")

        candidates = self._reader.find(query, limit)
        if not candidates:
            return Resolution(query=query)

        exact = [node for node in candidates if self._is_exact(node, query)]
        if len(exact) == 1:
            return Resolution(query=query, node=exact[0], candidates=tuple(candidates))
        if len(candidates) == 1:
            return Resolution(query=query, node=candidates[0], candidates=tuple(candidates))
        return Resolution(query=query, candidates=tuple(candidates))

    @staticmethod
    def _is_exact(node: NodeSummary, query: str) -> bool:
        """Casa a chave ou o rotulo, sem diferenciar maiuscula.

        A chave de um endpoint traz o repo (`forge-api:GET /itens`), entao
        perguntar so pela rota tem de casar pelo rotulo tambem.
        """
        wanted = query.casefold()
        return node.key.casefold() == wanted or node.label.casefold() == wanted
