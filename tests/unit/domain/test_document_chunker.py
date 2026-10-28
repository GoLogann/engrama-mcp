from itertools import pairwise

from engrama.domain.services import DocumentChunker


def chunk_text(text, **kwargs):
    return DocumentChunker(**kwargs).chunks(text)


def test_corta_por_titulo_e_guarda_a_faixa_de_linhas():
    text = "\n".join(
        [
            "# PhishForge",  # 1
            "",
            "Ferramenta educacional.",  # 3
            "",
            "## Instalacao",  # 5
            "",
            "Rode o compose.",  # 7
        ]
    )

    chunks = chunk_text(text, max_chars=40)

    assert [(c.index, c.first_line, c.last_line) for c in chunks] == [(0, 1, 3), (1, 5, 7)]
    assert chunks[0].heading == "PhishForge"
    assert chunks[0].text.startswith("# PhishForge")


def test_titulo_carrega_a_trilha_de_niveis():
    text = "# API\n\n## Rotas\n\ntexto\n\n### Pistas\n\nmais\n\n## Bancos\n\nfim"

    headings = [c.heading for c in chunk_text(text, max_chars=20)]

    assert headings == ["API", "API > Rotas", "API > Rotas > Pistas", "API > Bancos"]


def test_junta_secoes_curtas_ate_o_limite():
    text = "# a\n\nx\n\n## b\n\ny\n\n## c\n\nz"

    chunks = chunk_text(text, max_chars=1000)

    assert len(chunks) == 1
    assert chunks[0].first_line == 1
    assert chunks[0].last_line == 11
    assert chunks[0].heading == "a"


def test_cerquilha_dentro_de_bloco_de_codigo_nao_e_titulo():
    text = "\n".join(
        [
            "# Instalacao",  # 1
            "",
            "```bash",  # 3
            "# copie o env",  # 4
            "cp .env.example .env",  # 5
            "```",  # 6
        ]
    )

    chunks = chunk_text(text, max_chars=1000)

    assert len(chunks) == 1
    assert "# copie o env" in chunks[0].text


def test_secao_maior_que_o_limite_e_cortada_em_linhas():
    body = "\n".join(f"linha {n} com texto suficiente para somar" for n in range(1, 11))

    chunks = chunk_text(f"# Titulo\n{body}", max_chars=120)

    assert len(chunks) > 1
    assert all(len(c.text) <= 120 for c in chunks)
    assert all(c.heading == "Titulo" for c in chunks)
    # As faixas de linha seguem em ordem e nao se sobrepoem.
    assert [c.first_line for c in chunks] == sorted(c.first_line for c in chunks)
    assert all(a.last_line < b.first_line for a, b in pairwise(chunks))


def test_texto_sem_titulo_nenhum_vira_um_chunk():
    chunks = chunk_text("so prosa\nem duas linhas", max_chars=1000)

    assert len(chunks) == 1
    assert chunks[0].heading == ""
    assert (chunks[0].first_line, chunks[0].last_line) == (1, 2)


def test_arquivo_que_nao_e_markdown_ignora_titulos():
    text = "flyway.url=jdbc:postgresql://host:5432/db\n# comentario\nflyway.user=app"

    chunks = DocumentChunker(max_chars=1000).chunks(text, markdown=False)

    assert len(chunks) == 1
    assert chunks[0].heading == ""
    assert chunks[0].text == text


def test_documento_vazio_nao_gera_chunk():
    assert chunk_text("") == ()
    assert chunk_text("\n\n   \n") == ()


def test_ultima_linha_ignora_linhas_vazias_do_fim():
    chunks = chunk_text("# t\n\ntexto\n\n\n\n", max_chars=1000)

    assert chunks[0].last_line == 3


def test_fim_de_linha_do_windows_nao_entra_no_texto():
    chunks = chunk_text("# t\r\n\r\ntexto\r\n", max_chars=1000)

    assert "\r" not in chunks[0].text
    assert chunks[0].last_line == 3
