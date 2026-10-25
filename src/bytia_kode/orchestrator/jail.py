"""Jail del worker: save/restore del estado global del registry (F2/T8).

El jail del registry es estado global de módulo (R5). Los workers son
secuenciales, así que un save/restore explícito alrededor de cada uno es
race-free. El worker queda confinado a su `scratch/` y sin trusted paths:
no hereda `~/.bytia-kode`, que expondría las SQLite de sesión.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from bytia_kode.tools import registry


@contextmanager
def worker_jail(scratch: Path):
    state = registry.snapshot_workspace_policy()
    try:
        registry.set_workspace_mode("confined")
        registry.set_workspace_root(Path(scratch))
        registry.replace_trusted_paths([])
        yield
    finally:
        registry.restore_workspace_policy(state)
