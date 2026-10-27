from collections.abc import Sequence

from engrama.application.dto.ingestion import CodeFacts, RepositoryFacts, RepositorySpec
from engrama.application.ports.sources import CodeExtractor, SourceRepository


class IngestRepository:
    """Leva um repo ao commit do catalogo e roda os extratores que se aplicam a ele."""

    def __init__(self, sources: SourceRepository, extractors: Sequence[CodeExtractor]) -> None:
        self._sources = sources
        self._extractors = extractors

    def execute(self, spec: RepositorySpec) -> RepositoryFacts:
        tree = self._sources.checkout(spec.repo)
        facts = CodeFacts()
        for extractor in self._extractors:
            if extractor.supports(spec):
                facts = facts.merged(extractor.extract(tree, spec))
        return RepositoryFacts(spec=spec, committed_at=tree.committed_at, facts=facts)
