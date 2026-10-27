from dataclasses import dataclass
from enum import StrEnum

from engrama.domain.errors import InvalidEvidence, InvalidProvenance


class Source(StrEnum):
    """De onde veio uma afirmacao do grafo."""

    EXTRACTION = "extraction"
    DOCUMENT = "document"
    LLM = "llm"
    PERSON = "person"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class Evidence:
    """Onde uma afirmacao pode ser conferida: um trecho de codigo ou um documento.

    Use `in_code` ou `in_document`; o construtor so valida.
    """

    repo: str | None = None
    path: str | None = None
    line: int | None = None
    commit: str | None = None
    url: str | None = None

    def __post_init__(self) -> None:
        in_code = self.repo is not None or self.path is not None
        if in_code and not (self.repo and self.path and self.commit):
            raise InvalidEvidence("evidencia no codigo exige repo, arquivo e commit")
        if not in_code and not self.url:
            raise InvalidEvidence("evidencia exige um trecho de codigo ou um link")
        if self.line is not None and self.line < 1:
            raise InvalidEvidence(f"linha invalida: {self.line}")

    @classmethod
    def in_code(cls, repo: str, path: str, commit: str, line: int | None = None) -> "Evidence":
        return cls(repo=repo, path=path, line=line, commit=commit)

    @classmethod
    def in_document(cls, url: str) -> "Evidence":
        return cls(url=url)

    def __str__(self) -> str:
        if self.url:
            return self.url
        location = f"{self.repo}/{self.path}"
        if self.line is not None:
            location += f":{self.line}"
        return f"{location}@{self.commit[:7]}"


@dataclass(frozen=True, slots=True)
class Provenance:
    """Origem, evidencia e confianca de uma aresta ou episodio (principio 1 do doc).

    Extracao deterministica e a unica origem com confianca alta; o que o LLM
    infere nunca chega a alta. So pessoas podem afirmar algo sem evidencia
    externa, porque o proprio episodio, com autor e data, e a evidencia.
    """

    source: Source
    confidence: Confidence
    evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        if self.source is not Source.PERSON and not self.evidence:
            raise InvalidProvenance(f"origem {self.source} exige ao menos uma evidencia")
        if self.source is Source.EXTRACTION and self.confidence is not Confidence.HIGH:
            raise InvalidProvenance("extracao deterministica tem confianca alta")
        if self.source is Source.LLM and self.confidence is Confidence.HIGH:
            raise InvalidProvenance("inferencia por LLM nunca tem confianca alta")

    @classmethod
    def extracted(cls, *evidence: Evidence) -> "Provenance":
        return cls(Source.EXTRACTION, Confidence.HIGH, evidence)

    @classmethod
    def from_document(cls, *evidence: Evidence) -> "Provenance":
        return cls(Source.DOCUMENT, Confidence.MEDIUM, evidence)

    @classmethod
    def inferred(
        cls, *evidence: Evidence, confidence: Confidence = Confidence.MEDIUM
    ) -> "Provenance":
        return cls(Source.LLM, confidence, evidence)

    @classmethod
    def stated_by_person(cls, *evidence: Evidence) -> "Provenance":
        return cls(Source.PERSON, Confidence.HIGH, evidence)
