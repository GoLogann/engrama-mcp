import re

from engrama.domain.errors import InvalidRoute
from engrama.domain.value_objects import HttpMethod, HttpRoute

_SCHEME_AND_HOST = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^/]*")
# Estilos de parametro das quatro stacks: `${expr}` (TS), `$nome` (Dart),
# `:nome` (Gin), `<nome>`/`<tipo:nome>` (Flask/Starlette) e `{nome}` (FastAPI).
_TEMPLATE_PARAM = re.compile(r"\$\{([^}]*)\}")
_DOLLAR_PARAM = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
_COLON_PARAM = re.compile(r"(?<=/):([A-Za-z_][A-Za-z0-9_]*)")
_ANGLE_PARAM = re.compile(r"<(?:[A-Za-z_]+:)?([A-Za-z_][A-Za-z0-9_]*)>")


def _param_name(expression: str) -> str:
    """`jobId` -> `jobId`; `item.id` -> `item_id`; expressao vazia -> `param`."""
    return re.sub(r"\W+", "_", expression).strip("_") or "param"


class RouteNormalizer:
    """Leva o caminho como aparece no codigo para a forma canonica da ontologia."""

    def normalize(self, raw: str) -> str:
        path = _SCHEME_AND_HOST.sub("", raw.strip())
        path = _TEMPLATE_PARAM.sub(lambda m: "{" + _param_name(m.group(1)) + "}", path)
        path = re.split(r"[?#]", path, maxsplit=1)[0]
        path = _DOLLAR_PARAM.sub(r"{\1}", path)
        path = _COLON_PARAM.sub(r"{\1}", path)
        path = _ANGLE_PARAM.sub(r"{\1}", path)
        segments = [segment for segment in path.split("/") if segment]
        return "/" + "/".join(segments)

    def join(self, *parts: str) -> str:
        return self.normalize("/".join(part for part in parts if part))

    def route(self, method: str, *parts: str) -> HttpRoute:
        try:
            http_method = HttpMethod(method.upper())
        except ValueError as error:
            raise InvalidRoute(f"metodo HTTP desconhecido: {method}") from error
        return HttpRoute(http_method, self.join(*parts))
