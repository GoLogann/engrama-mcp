from dataclasses import replace

from engrama.application.dto.documentation import RepositoryDocuments
from engrama.application.dto.ingestion import RepositorySpec
from engrama.application.ports.sources import DocumentExtractor, SourceRepository
from engrama.application.ports.system import SecretScanner


class ReadRepositoryDocuments:
    """Le os documentos de um repo no commit do catalogo e mascara os segredos.

    A mascara e aplicada aqui, antes de o texto virar no do grafo, que e o
    ponto onde `docs/seguranca.md` manda mascarar. As rotas citadas saem do
    texto original: mascarar `senha=x` nao muda nenhuma rota, e o que o grafo
    guarda e sempre a versao mascarada.
    """

    def __init__(
        self,
        sources: SourceRepository,
        extractor: DocumentExtractor,
        scanner: SecretScanner,
    ) -> None:
        self._sources = sources
        self._extractor = extractor
        self._scanner = scanner

    def execute(self, spec: RepositorySpec) -> RepositoryDocuments:
        tree = self._sources.checkout(spec.repo)
        facts = self._extractor.extract(tree, spec)

        documents = []
        redactions: list[str] = []
        for document in facts.documents:
            redaction = self._scanner.redact(document.text)
            redactions += [
                f"{spec.repo.name}/{document.path}:{finding.line}: {finding.rule}"
                for finding in redaction.findings
            ]
            documents.append(replace(document, text=redaction.text))

        return RepositoryDocuments(
            spec=spec,
            committed_at=tree.committed_at,
            facts=replace(facts, documents=tuple(documents)),
            redactions=tuple(redactions),
        )
