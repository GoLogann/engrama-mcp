import re
from collections.abc import Iterator
from dataclasses import dataclass

# Titulo ATX (`## Contexto`). O que vem depois de ``` ou ~~~ e codigo: um `#`
# dentro de um bloco de codigo e comentario de shell, nao titulo.
_HEADING = re.compile(r"^(?P<level>#{1,6})\s+(?P<text>.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(?P<fence>```+|~~~+)")


@dataclass(frozen=True, slots=True)
class Heading:
    level: int
    text: str


def scan_headings(lines: list[str]) -> Iterator[tuple[int, str, Heading | None]]:
    """Cada linha com seu numero (1-based) e, se for titulo, o titulo.

    Dentro de bloco de codigo nada e titulo: num README cheio de shell, `#` e
    comentario. Quem le o texto do documento (chunker, leitura do titulo) usa
    esta mesma passagem, para as duas nao discordarem.
    """
    in_code = False
    fence = ""
    for number, line in enumerate(lines, start=1):
        if marker := _FENCE.match(line):
            if not in_code:
                in_code, fence = True, marker.group("fence")[:3]
            elif marker.group("fence").startswith(fence):
                in_code = False
            yield number, line, None
            continue
        title = None if in_code else _HEADING.match(line)
        heading = Heading(len(title.group("level")), title.group("text")) if title else None
        yield number, line, heading


def first_heading(text: str) -> str | None:
    """O primeiro titulo do documento, que serve de titulo dele."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return next((h.text for _, _, h in scan_headings(lines) if h is not None), None)


@dataclass(frozen=True, slots=True)
class TextChunk:
    """Pedaco de texto com a faixa de linhas de onde saiu, 1-based.

    `heading` e a trilha de titulos ate aqui (`Instalacao > Docker`), que da
    contexto ao pedaco sem precisar do documento inteiro.
    """

    index: int
    text: str
    first_line: int
    last_line: int
    heading: str = ""


@dataclass(frozen=True, slots=True)
class _Section:
    heading: str
    first_line: int
    lines: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


class DocumentChunker:
    """Corta um documento em pedacos indexaveis, preservando as linhas.

    Em Markdown a unidade e a secao de um titulo: secoes curtas seguidas sao
    juntadas ate `max_chars`, e uma secao maior que isso e cortada em limites
    de linha. Em arquivo que nao e Markdown (`flyway.config`, `package.json`)
    nao existe titulo, e o corte e so por tamanho.

    A faixa de linhas e o que permite citar a fonte como `repo/caminho:linha`,
    no mesmo formato das perguntas de ouro.
    """

    def __init__(self, max_chars: int = 1500) -> None:
        self._max_chars = max_chars

    def chunks(self, text: str, *, markdown: bool = True) -> tuple[TextChunk, ...]:
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        sections = self._sections(lines) if markdown else self._single_section(lines)
        return tuple(
            TextChunk(index, chunk.text, chunk.first_line, last, chunk.heading)
            for index, (chunk, last) in enumerate(self._packed(sections))
        )

    def _sections(self, lines: list[str]) -> list[_Section]:
        sections: list[_Section] = []
        trail: list[str] = []
        current: list[str] = []
        heading, first_line = "", 1

        def close() -> None:
            if any(line.strip() for line in current):
                sections.append(_Section(heading, first_line, tuple(current)))

        for number, line, title in scan_headings(lines):
            if title is None:
                current.append(line)
            else:
                close()
                trail = [*trail[: title.level - 1], title.text]
                heading, first_line, current = " > ".join(trail), number, [line]
        close()
        return sections

    def _single_section(self, lines: list[str]) -> list[_Section]:
        if not any(line.strip() for line in lines):
            return []
        return [_Section("", 1, tuple(lines))]

    def _packed(self, sections: list[_Section]) -> list[tuple[_Section, int]]:
        """Junta secoes consecutivas ate `max_chars` e corta as grandes.
        Devolve cada pedaco com a ultima linha que de fato tem conteudo."""
        packed: list[_Section] = []
        for section in sections:
            for piece in self._split(section):
                merged = self._merge(packed[-1], piece) if packed else None
                if merged is None:
                    packed.append(piece)
                else:
                    packed[-1] = merged
        return [(piece, self._last_line(piece)) for piece in packed]

    def _merge(self, previous: _Section, piece: _Section) -> _Section | None:
        """Os dois pedacos juntos, ou None se nao couberem em `max_chars`.
        O titulo e a primeira linha sao os do pedaco anterior."""
        lines = (*previous.lines, *piece.lines)
        if sum(len(line) + 1 for line in lines) - 1 > self._max_chars:
            return None
        return _Section(previous.heading, previous.first_line, lines)

    def _split(self, section: _Section) -> list[_Section]:
        if len(section.text) <= self._max_chars:
            return [section]
        pieces: list[_Section] = []
        buffer: list[str] = []
        start = section.first_line
        for offset, line in enumerate(section.lines):
            size = sum(len(item) + 1 for item in buffer)
            if buffer and size + len(line) > self._max_chars:
                pieces.append(_Section(section.heading, start, tuple(buffer)))
                start, buffer = section.first_line + offset, []
            buffer.append(line)
        if any(line.strip() for line in buffer):
            pieces.append(_Section(section.heading, start, tuple(buffer)))
        return pieces

    @staticmethod
    def _last_line(section: _Section) -> int:
        """A ultima linha com conteudo: um pedaco nao termina em linhas vazias."""
        content = [
            number
            for number, line in enumerate(section.lines, start=section.first_line)
            if line.strip()
        ]
        return content[-1] if content else section.first_line
