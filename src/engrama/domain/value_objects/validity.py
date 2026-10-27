from dataclasses import dataclass, replace
from datetime import datetime

from engrama.domain.errors import InvalidValidity


@dataclass(frozen=True, slots=True)
class Validity:
    """Modelo bitemporal (RASMUSSEN et al., 2025).

    `valid_from`/`valid_to` dizem quando o fato vale no mundo; `ingested_at`
    diz quando o grafo ficou sabendo. Um fato superado ganha `valid_to` e
    continua no grafo: nada e apagado.
    """

    valid_from: datetime
    ingested_at: datetime
    valid_to: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("valid_from", "ingested_at", "valid_to"):
            moment = getattr(self, name)
            if moment is not None and moment.tzinfo is None:
                raise InvalidValidity(f"{name} precisa de fuso horario")
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise InvalidValidity("valid_to anterior a valid_from")

    @classmethod
    def starting(cls, valid_from: datetime, ingested_at: datetime | None = None) -> "Validity":
        return cls(valid_from=valid_from, ingested_at=ingested_at or valid_from)

    @property
    def is_open(self) -> bool:
        return self.valid_to is None

    def holds_at(self, moment: datetime) -> bool:
        return self.valid_from <= moment and (self.valid_to is None or moment < self.valid_to)

    def closed_at(self, moment: datetime) -> "Validity":
        if not self.is_open:
            raise InvalidValidity("validade ja encerrada")
        return replace(self, valid_to=moment)
