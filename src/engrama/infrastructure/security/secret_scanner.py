import re
from pathlib import PurePosixPath

from detect_secrets.core.scan import scan_line
from detect_secrets.settings import default_settings

from engrama.application.ports.system import Redaction, SecretFinding, SecretScanner

REDACTED = "<redacted>"

_EXCLUDED_DIRS = {"node_modules", "build", "dist", ".dart_tool"}
_EXCLUDED_SUFFIXES = {
    ".pem", ".key", ".p12", ".pfx", ".exe", ".so", ".dll", ".jar", ".bin",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".svg", ".pdf", ".snapshot",
}  # fmt: skip
_RAW_REPORT = re.compile(r"_\d{8}_\d{6}\.json$")

_SENSITIVE_KEY = (
    r"[A-Za-z0-9_]*(?:PASSWORD|PASSWD|PASSPHRASE|SECRET|SALT|TOKEN|API_?KEY|PRIVATE_KEY|CREDENTIAL)"
    r"[A-Za-z0-9_]*"
)
_KEY_VALUE = re.compile(
    rf"(?i)\b(?P<key>{_SENSITIVE_KEY})(?P<sep>\s*(?::=|[:=])\s*)"
    r"""(?:"(?P<dq>[^"]*)"|'(?P<sq>[^']*)'|(?P<bare>[^\s"'#,;)]+))"""
)
_URL_CREDENTIALS = re.compile(r"(?P<prefix>\b[a-z][a-z0-9+.-]*://[^/\s:@]+:)[^@\s/]+(?=@)")
# `${VAR:-padrao}`, `${VAR-padrao}` e `${VAR:=padrao}`: a variavel e uma referencia,
# mas o padrao que o compose embute e um valor de verdade e vai para o repositorio.
_ENV_DEFAULT = re.compile(r"^\$\{(?P<name>\w+)(?P<op>:?[-=])(?P<default>[^$}][^}]*)\}$")
# Valores que sao referencias ou nomes de tipo, nao segredos: `${VAR:-}`,
# `$VAR`, `settings.DB_PASSWORD`, `password: str`.
_NOT_A_VALUE = re.compile(
    r"^(?:\$|<|\{|\w+\.\w|\w+\()|^(?:str|string|int|bool|None|null|true|false)$"
)
_MIN_GENERIC_LENGTH = 16
# Do detect-secrets ficam so os detectores de provedor (AWS, GitHub, chave
# privada, JWT...). Palavra-chave ja e coberta pela regra de chave=valor, e os
# de entropia, chamados linha a linha pelo `scan_line`, nao aplicam limiar:
# marcam ate `passwordController` e `text`.
_SKIPPED_DETECTORS = {"Secret Keyword", "Base64 High Entropy String", "Hex High Entropy String"}


class RegexSecretScanner(SecretScanner):
    """Implementa as regras de docs/seguranca.md: regras proprias para
    chave=valor, strings de conexao e literais, mais o detect-secrets para o
    que nenhuma regra preve (tokens de provedores, alta entropia)."""

    def excludes(self, path: str) -> bool:
        pure = PurePosixPath(path)
        if any(part in _EXCLUDED_DIRS for part in pure.parts[:-1]):
            return True
        name = pure.name
        if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
            return True
        if name.startswith("id_rsa") or pure.suffix.lower() in _EXCLUDED_SUFFIXES:
            return True
        return bool(_RAW_REPORT.search(name))

    def redact(self, text: str) -> Redaction:
        findings: list[SecretFinding] = []
        lines = text.split("\n")
        with default_settings():
            for number, line in enumerate(lines, start=1):
                redacted, rules = self._redact_line(line)
                lines[number - 1] = redacted
                findings.extend(SecretFinding(rule, number) for rule in rules)
        return Redaction(text="\n".join(lines), findings=tuple(findings))

    def _redact_line(self, line: str) -> tuple[str, list[str]]:
        rules: list[str] = []

        def mask_value(match: re.Match[str]) -> str:
            value = match.group("dq") or match.group("sq") or match.group("bare") or ""
            quote = '"' if match.group("dq") is not None else "'" if match.group("sq") else ""
            head = f"{match.group('key')}{match.group('sep')}{quote}"
            if default := _ENV_DEFAULT.match(value):
                rules.append("env-default")
                return f"{head}${{{default['name']}{default['op']}{REDACTED}}}{quote}"
            if not value or _NOT_A_VALUE.search(value):
                return match.group(0)
            if value.lower() == match.group("key").lower():
                # `OpenAI(api_key=api_key)`: parametro repassado, nao segredo.
                # Mascarar estraga exemplo de codigo na documentacao, e o unico
                # "segredo" que isso deixa passar e a propria palavra da chave.
                return match.group(0)
            rules.append("key-value")
            return f"{head}{REDACTED}{quote}"

        line = _KEY_VALUE.sub(mask_value, line)
        line, count = _URL_CREDENTIALS.subn(rf"\g<prefix>{REDACTED}", line)
        rules.extend(["url-credentials"] * count)
        for secret in scan_line(line):
            if secret.type in _SKIPPED_DETECTORS:
                continue
            value = secret.secret_value or ""
            if len(value) >= _MIN_GENERIC_LENGTH and value in line and REDACTED not in value:
                line = line.replace(value, REDACTED)
                rules.append(secret.type)
        return line, rules
