"""Os modulos do grafo contra os clones reais.

Os 98 modulos nao tem groundtruth escrito a mao — seria conferir 98 caminhos
derivados mecanicamente da lista de arquivos versionados. O que da para
garantir, e o que esta aqui, e que a derivacao nunca inventa diretorio: todo
modulo que a extracao produz existe no clone. O que sobra e a *regra de
agrupamento* (um modulo por diretorio de arquivo de codigo), que e escolha
documentada, nao erro possivel.

Sem os clones em `.cache/repos` (criados por `engrama ingest`), e pulado.
"""

from pathlib import Path

import pytest

from engrama.infrastructure.config.yaml_catalog import YamlRepositoryCatalog
from engrama.infrastructure.extractors.base import ROOT_MODULE, module_of

ROOT = Path(__file__).parents[2]
REPOS = ROOT / ".cache" / "repos"
CODE_SUFFIXES = (".py", ".go", ".ts", ".tsx", ".js", ".dart")

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def repos() -> list[str]:
    if not REPOS.is_dir():
        pytest.skip(f"clones ausentes em {REPOS}; rode `engrama ingest`")
    names = list(YamlRepositoryCatalog(ROOT / "config" / "repos.yaml").load().repo_names)
    missing = [name for name in names if not (REPOS / name).is_dir()]
    if missing:
        pytest.skip(f"clones ausentes: {', '.join(missing)}")
    return names


def test_todo_modulo_derivado_existe_como_diretorio_no_clone(repos):
    inexistentes: list[str] = []
    total = 0
    for name in repos:
        clone = REPOS / name
        for path in clone.rglob("*"):
            if not path.is_file() or path.suffix not in CODE_SUFFIXES:
                continue
            if ".git" in path.parts:
                continue
            relative = path.relative_to(clone).as_posix()
            module = module_of(relative)
            total += 1
            if module == ROOT_MODULE:
                continue
            if not (clone / module).is_dir():
                inexistentes.append(f"{name}/{module} (de {relative})")

    assert total > 0, "nenhum arquivo de codigo encontrado nos clones"
    assert inexistentes == [], f"modulos sem diretorio: {inexistentes[:10]}"


def test_a_raiz_do_repo_e_um_modulo_com_nome_proprio(repos):
    """Arquivo na raiz nao vira modulo de nome vazio, que o Neo4j aceitaria e
    nenhuma resposta saberia citar."""
    assert module_of("main.go") == ROOT_MODULE
    assert ROOT_MODULE.strip()
    assert module_of("app/api/items.py") == "app/api"
