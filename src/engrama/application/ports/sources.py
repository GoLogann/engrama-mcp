from abc import ABC, abstractmethod
from collections.abc import Collection, Iterator
from datetime import datetime

from engrama.application.dto.ingestion import Catalog, CodeFacts, RepositorySpec
from engrama.domain.entities import Repo


class RepositoryCatalog(ABC):
    """Quais projetos e repos o engrama conhece, e em qual commit."""

    @abstractmethod
    def load(self) -> Catalog: ...


class SourceTree(ABC):
    """Arvore de arquivos de um repo num commit. Arquivos que a politica de
    segredos exclui nunca aparecem aqui."""

    repo: Repo

    @property
    @abstractmethod
    def committed_at(self) -> datetime: ...

    @abstractmethod
    def files(self, suffixes: Collection[str], exclude_dirs: Collection[str] = ()) -> Iterator[str]:
        """Caminhos relativos a raiz, em ordem, com uma das extensoes."""

    @abstractmethod
    def read(self, path: str) -> str: ...


class SourceRepository(ABC):
    @abstractmethod
    def checkout(self, repo: Repo) -> SourceTree:
        """Deixa o repo no commit do catalogo e devolve a arvore de arquivos."""


class CodeExtractor(ABC):
    """Extrai fatos de uma stack. Uma stack nova e uma subclasse nova
    registrada no container; o pipeline nao muda (aberto/fechado)."""

    @abstractmethod
    def supports(self, spec: RepositorySpec) -> bool: ...

    @abstractmethod
    def extract(self, tree: SourceTree, spec: RepositorySpec) -> CodeFacts: ...
