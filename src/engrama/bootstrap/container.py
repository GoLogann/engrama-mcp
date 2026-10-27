from dependency_injector import containers, providers

from engrama.bootstrap.settings import Settings


class Container(containers.DeclarativeContainer):
    """Raiz de composicao: o unico lugar que conhece as classes concretas.

    Casos de uso recebem portas pelo construtor; aqui cada porta e ligada ao
    seu adapter. Trocar Neo4j, LLM ou embedder e mudar uma linha deste arquivo.
    """

    settings = providers.Singleton(Settings)
