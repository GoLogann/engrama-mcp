import re
from dataclasses import dataclass
from enum import StrEnum

from engrama.domain.errors import InvalidRoute

# Forma canonica: comeca com "/", sem barra final, sem query string, e
# parametros no estilo `{nome}`. Quem converte `:id`, `${id}` ou `$id` para
# essa forma e o RouteNormalizer (fase 1); aqui so se garante o resultado.
_SEGMENT = r"(?:[A-Za-z0-9._~-]+|\{[A-Za-z_][A-Za-z0-9_]*\})"
_CANONICAL_PATH = re.compile(rf"^/(?:{_SEGMENT}(?:/{_SEGMENT})*)?$")
_PARAM = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


@dataclass(frozen=True, slots=True)
class HttpRoute:
    method: HttpMethod
    path: str

    def __post_init__(self) -> None:
        if not _CANONICAL_PATH.match(self.path):
            raise InvalidRoute(f"rota fora da forma canonica: {self.path!r}")

    @property
    def shape(self) -> str:
        """Metodo e caminho sem os nomes dos parametros: o que se compara ao casar
        uma chamada com uma rota (`/items/{id}` e `/items/{item_id}` sao a mesma)."""
        return f"{self.method} {_PARAM.sub('{}', self.path)}"

    def __str__(self) -> str:
        return f"{self.method} {self.path}"
