import re
from pathlib import PurePosixPath

from engrama.application.dto.documentation import DocumentFacts
from engrama.application.dto.ingestion import RepositorySpec
from engrama.application.ports.sources import DocumentExtractor, SourceTree
from engrama.domain.errors import InvalidRoute
from engrama.domain.services import RouteNormalizer, first_heading
from engrama.domain.value_objects import Evidence
from engrama.domain.value_objects.document_facts import DocumentFile, DocumentKind, RouteMention

# `.conf.template` precisa estar explicito: ele termina em `.template`, e nao
# em `.conf`, e o casamento e por fim de nome. `.cfg` e `.ini` ficaram de fora
# porque nenhum arquivo dos quatro repos usa — a regra enumera o que existe
# (ADR 0010), e nao o que poderia existir.
SUFFIXES = (".md", ".config", ".conf", ".conf.template")
ROOT_FILES = ("package.json",)
# Diretorios cujo conteudo nao e documentacao do projeto: dados de entrada
# (`data/articles/phishing_examples.md` sao exemplos de phishing, nao docs),
# pastas de plataforma do Flutter e material de teste. Indexar isso enche o
# indice de texto que nunca responde pergunta sobre o projeto.
EXCLUDED_DIRS = frozenset(
    {
        "data",
        "assets",
        "ios",
        "android",
        "macos",
        "windows",
        "linux",
        "web",
        "test",
        "tests",
        "__tests__",
        "testdata",
        "fixtures",
    }
)
DECISION_DIRS = frozenset({"decisoes", "decisions", "adr", "adrs"})

# `- **Status:** aceita`, `Status: proposta`.
_STATUS = re.compile(r"(?im)^\s*[-*]?\s*\**\s*status\s*\**\s*:\s*\**\s*(?P<status>.+?)\s*\**\s*$")
# Rota escrita no texto: `POST /api/v1/generate/batch`, `GET http://host/x`.
_MENTION = re.compile(
    r"\b(?P<method>GET|POST|PUT|PATCH|DELETE)\s+"
    r"(?P<path>(?:[a-z][a-z0-9+.-]*://[^\s`'\"<>)]+)?/[^\s`'\"<>)]*)"
)
# Pontuacao que fecha a frase, nao a rota. `}` fica de fora: e o fim de um
# parametro (`/emails/{email_id}`), e tirar vira rota fora da forma canonica.
_TRAILING = ".,;:!?)]`'\"*"


class RepositoryDocumentExtractor(DocumentExtractor):
    """Le a documentacao versionada de um repo: README, `docs/`, ADRs e os
    arquivos de configuracao que respondem perguntas (`migrate/flyway.config`,
    `package.json`).

    Decisao (ADR) e reconhecida pelo diretorio (`docs/decisoes/`), nao pelo
    conteudo: e deterministico e e a convencao dos repos do LABit. O titulo
    sai do primeiro titulo do arquivo, e o status, da linha "Status:" da
    propria decisao.
    """

    def __init__(self, normalizer: RouteNormalizer) -> None:
        self._normalizer = normalizer

    def extract(self, tree: SourceTree, spec: RepositorySpec) -> DocumentFacts:
        documents: list[DocumentFile] = []
        mentions: list[RouteMention] = []
        diagnostics: list[str] = []
        for path in self._paths(tree):
            text = tree.read(path)
            documents.append(self._document(spec, path, text))
            found, warnings = self._mentions(spec, path, text)
            mentions += found
            diagnostics += warnings
        return DocumentFacts(tuple(documents), tuple(mentions), tuple(diagnostics))

    def _paths(self, tree: SourceTree) -> list[str]:
        paths = [
            path
            for path in tree.files(SUFFIXES, EXCLUDED_DIRS)
            if not PurePosixPath(path).name.startswith(".")
        ]
        paths += [name for name in ROOT_FILES if self._has(tree, name)]
        return sorted(paths)

    @staticmethod
    def _has(tree: SourceTree, name: str) -> bool:
        """So o arquivo da raiz: `package.json` de subprojeto nao e documentacao."""
        return any(path == name for path in tree.files((name,)))

    def _document(self, spec: RepositorySpec, path: str, text: str) -> DocumentFile:
        pure = PurePosixPath(path)
        kind = (
            DocumentKind.DECISION
            if any(part in DECISION_DIRS for part in pure.parts[:-1])
            else DocumentKind.DOC
        )
        status = None
        if kind is DocumentKind.DECISION and (found := _STATUS.search(text)):
            status = found.group("status")
        return DocumentFile(
            repo=spec.repo.name,
            path=path,
            kind=kind,
            title=first_heading(text) or pure.name,
            text=text,
            evidence=Evidence.in_code(spec.repo.name, path, spec.repo.commit),
            status=status,
        )

    def _mentions(
        self, spec: RepositorySpec, path: str, text: str
    ) -> tuple[list[RouteMention], list[str]]:
        found: dict[tuple[int, str], RouteMention] = {}
        diagnostics: list[str] = []
        for match in _MENTION.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            raw = match.group("path").rstrip(_TRAILING)
            try:
                route = self._normalizer.route(match.group("method"), raw)
            except InvalidRoute as error:
                diagnostics.append(f"{spec.repo.name}/{path}:{line}: {error}; citacao ignorada")
                continue
            evidence = Evidence.in_code(spec.repo.name, path, spec.repo.commit, line)
            found.setdefault(
                (line, str(route)), RouteMention(spec.repo.name, path, route, evidence)
            )
        return list(found.values()), diagnostics
