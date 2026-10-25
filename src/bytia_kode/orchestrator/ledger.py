"""Workspace y estado compartido del orquestador (F1).

El ledger es el estado que leen las instancias frescas: ficheros del
workspace, registro append-only (``record.jsonl``), lista de tareas y SHA
base. Todas las escrituras de estado son atómicas (tmp + ``os.replace``):
un fallo a mitad no puede dejar el fichero corrupto ni a medias.
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from pathlib import Path

_META_FILE = "meta.json"


class Ledger:
    """Estado compartido del workspace con escrituras atómicas."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # -- ficheros de texto -------------------------------------------------
    def write_text(self, name: str, content: str) -> None:
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        # Nombre temporal único por escritor: dos procesos que escriban el
        # mismo fichero no comparten el tmp (revisión F1, hallazgo 11).
        fd, tmp_name = tempfile.mkstemp(
            dir=target.parent, prefix=target.name + ".", suffix=".tmp"
        )
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, target)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise

    def read_text(self, name: str) -> str:
        target = self.root / name
        if not target.exists():
            return ""
        return target.read_text(encoding="utf-8")

    # -- registro append-only ---------------------------------------------
    def append_record(self, entry: dict) -> None:
        line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        with (self.root / "record.jsonl").open("a", encoding="utf-8") as handle:
            # Lock entre escritores (TUI y Telegram comparten el workspace).
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def record_entries(self) -> list[dict]:
        target = self.root / "record.jsonl"
        if not target.exists():
            return []
        entries: list[dict] = []
        for line in target.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entries.append(json.loads(stripped))
            except json.JSONDecodeError:
                # Línea truncada por un corte a mitad de append: se ignora.
                continue
        return entries

    # -- lista de tareas ---------------------------------------------------
    def write_tasks(self, tasks: list[dict]) -> None:
        self.write_text("tasks.json", json.dumps(tasks, ensure_ascii=False, indent=2))

    def read_tasks(self) -> list[dict]:
        raw = self.read_text("tasks.json")
        if not raw.strip():
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    # -- SHA base ----------------------------------------------------------
    def set_base_sha(self, sha: str) -> None:
        meta = self._read_meta()
        meta["base_sha"] = sha
        self.write_text(_META_FILE, json.dumps(meta, ensure_ascii=False, indent=2))

    def get_base_sha(self) -> str | None:
        return self._read_meta().get("base_sha")

    def _read_meta(self) -> dict:
        raw = self.read_text(_META_FILE)
        if not raw.strip():
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
