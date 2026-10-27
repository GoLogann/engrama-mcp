import pytest

from engrama.application.dto.ingestion import Catalog, RepositorySpec
from engrama.domain.entities import Project, Repo, Stack
from engrama.domain.errors import UnknownRepository

C = "f" * 40


def spec(name: str, consumes: tuple[str, ...] = ()) -> RepositorySpec:
    repo = Repo(name, "p", f"https://x/{name}", C, Stack.GO_GIN)
    return RepositorySpec(repo, consumes=consumes)


# front -> api;  admin -> api e auth;  docs sem relacao com ninguem.
CATALOG = Catalog(
    projects=(Project("p", "P"),),
    repos=(
        spec("front", ("api",)),
        spec("api"),
        spec("admin", ("api", "auth")),
        spec("auth"),
        spec("docs"),
    ),
)


def test_sem_selecao_vale_o_catalogo_inteiro():
    assert CATALOG.with_related(()) == ("front", "api", "admin", "auth", "docs")


def test_cliente_traz_os_servidores_que_consome():
    assert CATALOG.with_related(["front"]) == ("front", "api")


def test_servidor_traz_os_clientes_e_os_outros_servidores_deles():
    # admin consome api, entao entra; e admin tambem consome auth, que precisa estar
    # presente para as chamadas de admin continuarem casando.
    assert CATALOG.with_related(["api"]) == ("front", "api", "admin", "auth")


def test_repo_sem_relacao_so_entra_quando_pedido():
    assert CATALOG.with_related(["docs"]) == ("docs",)
    assert "docs" not in CATALOG.with_related(["api"])


def test_nome_desconhecido_e_recusado():
    with pytest.raises(UnknownRepository, match="apii"):
        CATALOG.with_related(["apii"])
