"""Estampa de build: el commit corto que distingue builds entre bumps.

`__version__` (pyproject + importlib.metadata) sólo cambia cuando alguien
bumpa la versión a mano, así que un editable sobre main y una instalación
vieja de PyPI son visualmente idénticas (hallazgo C6 / AST-20). Este módulo
añade el sufijo `+<hash>` resolviendo el commit por este orden:

1. ``_commit.txt`` junto al paquete — estampado en build time por el hook
   ``hatch_build.py`` (wheel/sdist construidos desde el repo).
2. ``git rev-parse --short HEAD`` en runtime — sólo cuando el paquete vive
   en un checkout (instalación editable). Dentro de site-packages nunca se
   consulta git: un wheel de PyPI en un venv dentro de un repo ajeno no
   debe heredar el hash de ese repo.
3. Sin estampa ni git (wheel de PyPI): sin sufijo. Nunca falla.

La resolución se cachea por proceso (`lru_cache`): ni git ni disco en cada
render del header.
"""
from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

_STAMP_NAME = "_commit.txt"
_HEX = frozenset("0123456789abcdef")


def _package_dir() -> Path:
    return Path(__file__).resolve().parent


def _clean_commit(raw: str) -> str | None:
    """Normaliza la salida a un hash corto válido, o None si es basura."""
    commit = raw.strip().lower()
    if 4 <= len(commit) <= 12 and set(commit) <= _HEX:
        return commit
    return None


def _read_stamp() -> str | None:
    """Commit estampado en build time junto al paquete, si el build lo dejó."""
    try:
        raw = (_package_dir() / _STAMP_NAME).read_text(encoding="utf-8")
    except OSError:
        return None
    return _clean_commit(raw)


def _in_site_packages() -> bool:
    return any(part in ("site-packages", "dist-packages") for part in _package_dir().parts)


def _runtime_commit() -> str | None:
    """Commit corto del checkout que contiene el paquete (modo editable)."""
    try:
        proc = subprocess.run(  # argv fijo, sin shell
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_package_dir(),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None  # sin git instalado, timeout, ...
    if proc.returncode != 0:
        return None  # no es un repo, HEAD roto, ...
    return _clean_commit(proc.stdout)


@lru_cache(maxsize=1)
def short_commit() -> str | None:
    """Commit corto del build, o None si no se puede determinar."""
    stamped = _read_stamp()
    if stamped:
        return stamped
    if _in_site_packages():
        return None  # instalación normal sin estampa (p.ej. PyPI): sin sufijo
    return _runtime_commit()


def version_suffix() -> str:
    return f"+{short_commit()}" if short_commit() else ""


def reset_cache() -> None:
    """Para tests: permite re-resolver tras cambiar el entorno."""
    short_commit.cache_clear()
