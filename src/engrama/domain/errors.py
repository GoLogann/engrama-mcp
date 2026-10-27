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


class ExcludedSourcePath(DomainError):
    """A politica de segredos (docs/seguranca.md) proibe ler este arquivo."""


class UnknownRepository(DomainError):
    """O nome pedido nao esta no catalogo (config/repos.yaml)."""


class EpisodeAlreadySuperseded(DomainError):
    """Um episodio encerrado nao pode ser substituido de novo: o historico e linear."""
