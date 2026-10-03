"""Build hook de hatchling: estampa el commit corto en wheel/sdist.

Escribe ``src/bytia_kode/_commit.txt`` antes de empaquetar y lo retira al
terminar para no ensuciar el árbol de trabajo (queda en ``.gitignore`` como
red de seguridad si un build aborta entre medias). En runtime,
``bytia_kode._build_info`` lo lee como fuente autoritativa del build id.

Sin git (o fuera de un repo): no se estampa hash nuevo y el build sigue
— degrada a la versión sin sufijo **sólo si tampoco hereda una estampa**
del sdist. OJO: un wheel sí puede salir con sufijo, porque más abajo se
re-incluye la estampa heredada pese al VCS-ignore; el wheel publicado de
PyPI la lleva (p.ej. ``0.8.4+91fb426``). Lo que degrada es el build sin
repo **y** sin estampa (AST-20).

La validación del hash vive duplicada en ``_build_info._clean_commit`` a
propósito: este fichero no puede importar el paquete en build time (el
``__init__`` arrastra dependencias que no existen en el entorno aislado
del builder).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

try:  # pragma: no cover - presente siempre en un build real (es el backend)
    from hatchling.builders.hooks.plugin.interface import BuildHookInterface
except ImportError:  # entornos sin hatchling (tests): sólo se ejercen los helpers
    class BuildHookInterface:  # type: ignore[no-redef]
        root = "."

_HEX = frozenset("0123456789abcdef")
_STAMP = Path("src") / "bytia_kode" / "_commit.txt"


def resolve_commit(root: Path) -> str | None:
    """Commit corto del checkout en ``root``, o None sin git / fallo."""
    if not (root / ".git").exists():
        return None  # no es un checkout: nunca estampar el hash de un repo ajeno
    try:
        proc = subprocess.run(  # argv fijo, sin shell
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    commit = proc.stdout.strip().lower()
    if 4 <= len(commit) <= 12 and set(commit) <= _HEX:
        return commit
    return None


def write_stamp(root: Path, commit: str) -> None:
    (root / _STAMP).write_text(commit + "\n", encoding="utf-8")


def clear_stamp(root: Path) -> None:
    (root / _STAMP).unlink(missing_ok=True)


def stamp_build(root: Path, build_data: dict) -> None:
    """Lógica del hook, separada de la clase para poder testearla sin hatchling."""
    commit = resolve_commit(root)
    if commit:
        write_stamp(root, commit)
    # Re-incluir la estampa (propia o heredada de un sdist) pese al
    # .gitignore: hatchling aplica VCS-ignores también al construir un
    # wheel desde un sdist desempaquetado, y sin esto la excluiría.
    if (root / _STAMP).exists():
        build_data.setdefault("artifacts", []).append(str(_STAMP))


class BuildStampHook(BuildHookInterface):
    def initialize(self, version, build_data) -> None:  # noqa: ANN001 - API de hatchling
        stamp_build(Path(self.root), build_data)

    def finalize(self, version, build_data, artifact) -> None:  # noqa: ANN001
        clear_stamp(Path(self.root))
