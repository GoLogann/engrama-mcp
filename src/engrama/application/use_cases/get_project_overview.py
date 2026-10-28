from engrama.application.dto.consulta import NodeSummary, ProjectOverview
from engrama.application.ports.graph import GraphReader


class GetProjectOverview:
    """Retrato de um projeto (tool `project_overview`).

    Hoje o retrato vem so da estrutura extraida: repos, modulos, endpoints,
    bancos e os READMEs. O resumo `simples` ou `tecnico` que o plano preve
    depende dos resumos por LLM da Fase 2; enquanto eles nao existem,
    `has_summary` e falso e quem apresenta diz isso, em vez de devolver um
    retrato que parece completo.
    """

    def __init__(self, reader: GraphReader) -> None:
        self._reader = reader

    def execute(self, project: str) -> ProjectOverview | None:
        return self._reader.overview(project.strip()) if project.strip() else None


class FindNode:
    """Resolve um nome para os nos que casam (tool `find`).

    Devolve a lista, e nao um no so: quem pergunta "ranking" pode querer a
    rota, o modulo ou o documento, e a tool existe justamente para mostrar as
    opcoes com a fonte de cada uma.
    """

    def __init__(self, reader: GraphReader) -> None:
        self._reader = reader

    def execute(self, text: str, limit: int = 10) -> list[NodeSummary]:
        query = text.strip()
        return self._reader.find(query, limit) if query and limit > 0 else []
