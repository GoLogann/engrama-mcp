class DomainError(Exception):
    """Base de toda violacao de regra do dominio."""


class InvalidEvidence(DomainError):
    pass


class InvalidProvenance(DomainError):
    pass


class InvalidValidity(DomainError):
    pass


class InvalidRoute(DomainError):
    pass


class InvalidNode(DomainError):
    pass


class InvalidEdge(DomainError):
    pass


class InvalidEpisode(DomainError):
    pass


class EpisodeAlreadySuperseded(DomainError):
    """Um episodio encerrado nao pode ser substituido de novo: o historico e linear."""
