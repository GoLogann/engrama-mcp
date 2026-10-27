import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path


def make_origin(tmp_path: Path, commits: Sequence[Mapping[str, str]]) -> tuple[Path, list[str]]:
    """Cria um repositorio git local, sem rede, com um commit por item de `commits`.

    Cada item e `{caminho: conteudo}` e soma ao anterior. Devolve o caminho do repo, que
    serve de `url` para `git clone`, e os SHAs na ordem dos commits. As datas sao fixas:
    `2026-10-0N 12:00 UTC` para o commit N.
    """
    origin = tmp_path / "origin"
    origin.mkdir()

    def git(*args: str, date: str | None = None) -> str:
        env = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date} if date else {}
        result = subprocess.run(
            ["git", "-c", "user.name=teste", "-c", "user.email=teste@example.org",
             "-c", "commit.gpgsign=false", *args],
            cwd=origin, check=True, capture_output=True, text=True,
            env={**os.environ, **env},
        )  # fmt: skip
        return result.stdout.strip()

    git("init", "-q", "-b", "main")
    shas = []
    for number, files in enumerate(commits, start=1):
        for path, content in files.items():
            target = origin / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        git("add", "-A", "-f")
        git("commit", "-q", "-m", f"commit {number}", date=f"2026-10-0{number}T12:00:00+00:00")
        shas.append(git("rev-parse", "HEAD"))
    return origin, shas
