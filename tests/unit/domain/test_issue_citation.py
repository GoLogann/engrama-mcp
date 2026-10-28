"""O leitor de citacoes de issue, que codigo e documento compartilham.

A regra central: citacao que aponta para outro repo e nao da para resolver
nunca cai no proprio repo. Gravar a issue errada com confianca alta e pior do
que nao gravar.
"""

import pytest

from engrama.domain.services import IssueCitationReader

REPOS = ("quest-api", "phishing_quest", "forge-api")


@pytest.fixture
def leitor() -> IssueCitationReader:
    return IssueCitationReader(REPOS)


def ler(leitor, linha, seguinte="", repo="quest-api", consumes=()):
    return leitor.read(linha, seguinte, own_repo=repo, consumes=consumes)


def test_issue_sem_qualificador_e_do_proprio_repo(leitor):
    report = ler(leitor, "// corrige a issue #7 do cadastro")

    assert [(c.repo, c.number) for c in report.found] == [("quest-api", 7)]


def test_lista_de_numeros_conta_todos(leitor):
    report = ler(leitor, "// ver issues #12 e #13")

    assert [c.number for c in report.found] == [12, 13]


def test_numero_solto_sem_a_palavra_issue_nao_conta(leitor):
    """`#6` sozinho e ambiguo demais — pode ser PR, ancora ou numero."""
    assert ler(leitor, "// combinado no comentario da #6").found == ()


def test_repo_nomeado_antes_do_numero_resolve(leitor):
    report = ler(leitor, "// ver forge-api #5 e #6")

    assert [(c.repo, c.number) for c in report.found] == [("forge-api", 5), ("forge-api", 6)]


def test_qualificador_com_nome_de_repo_entre_crases_resolve(leitor):
    report = ler(leitor, "// a issue #38 no repositorio `phishing_quest` cobre isso")

    assert [(c.repo, c.number) for c in report.found] == [("phishing_quest", 38)]


def test_do_backend_resolve_quando_consumes_tem_um_so(leitor):
    report = ler(leitor, "// issue #3 do backend", repo="phishing_quest", consumes=("quest-api",))

    assert [(c.repo, c.number) for c in report.found] == [("quest-api", 3)]


def test_do_backend_com_dois_consumes_nao_resolve(leitor):
    report = ler(leitor, "// issue #3 do backend", consumes=("forge-api", "phishing_quest"))

    assert report.found == ()
    assert report.unresolved == (3,)


def test_qualificador_generico_de_cliente_nao_cai_no_proprio_repo(leitor):
    """`consumes` lista quem o repo consome, nao quem o consome: nao ha como
    resolver "do app" a partir dele."""
    report = ler(leitor, "// ajuste combinado na issue #10 do app")

    assert report.found == ()
    assert report.unresolved == (10,)


def test_participio_entre_o_numero_e_o_qualificador_ainda_conta(leitor):
    report = ler(leitor, "// issue #38 aberta no front, ja corrigida")

    assert report.unresolved == (38,)


def test_duas_palavras_antes_do_qualificador_nao_contam(leitor):
    report = ler(leitor, "// issue #7 e o front tambem usa isso")

    assert [(c.repo, c.number) for c in report.found] == [("quest-api", 7)]


def test_qualificador_na_linha_seguinte_vale(leitor):
    report = ler(leitor, "// ver issue #10 do", "repo quest-api). Ate que exista", repo="x")

    assert [(c.repo, c.number) for c in report.found] == [("quest-api", 10)]


def test_linha_seguinte_vazia_nao_continua_a_frase(leitor):
    """Quem chama decide o que e "logo depois"; aqui a vazia e o fim."""
    report = ler(leitor, "// ver issue #10 do", "")

    assert [(c.repo, c.number) for c in report.found] == [("quest-api", 10)]
