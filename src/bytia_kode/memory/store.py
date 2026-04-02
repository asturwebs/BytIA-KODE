"""BytMemory connector for persistent memory."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    key: str
    content: str
    tags: list[str] | None = None


class BytMemoryConnector:
    """Connects to BytMemory for persistent knowledge storage."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir / "memory"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._store: dict[str, str] = {}
        self._load()

    def _load(self):
        store_file = self.data_dir / "store.json"
        if store_file.exists():
            try:
                self._store = json.loads(store_file.read_text(encoding="utf-8"))
                logger.debug("Loaded %s memory entries", len(self._store))
            except json.JSONDecodeError as exc:
                logger.error("Memory store is corrupted: %s", exc)
                raise RuntimeError(f"Memory store is corrupted: {store_file}") from exc
            except Exception as exc:
                logger.error("Failed to load memory: %s", exc)
                raise RuntimeError(f"Failed to load memory store: {store_file}") from exc

    def _save(self):
        store_file = self.data_dir / "store.json"
        store_file.write_text(json.dumps(self._store, indent=2, ensure_ascii=False), encoding="utf-8")

    def add(self, key: str, content: str):
        self._store[key] = content
        self._save()

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def search(self, query: str, limit: int = 5) -> list[str]:
        """Simple keyword search. Can be upgraded to semantic search via FAISS."""
        results = []
        q = query.lower()
        for key, value in self._store.items():
            if q in key.lower() or q in value.lower():
                results.append(f"[{key}] {value}")
                if len(results) >= limit:
                    break
        return results

    def get_context(self) -> str:
        """Get a bounded slice of memory as context for system prompt."""
        if not self._store:
            return ""
        max_entries = 20
        max_chars = 2000
        lines = ["## Memory\n"]
        current_length = len(lines[0])
        selected_lines: list[str] = []
        for key, value in reversed(list(self._store.items())[-max_entries:]):
            line = f"- **{key}**: {value}"
            if current_length + len(line) + 1 > max_chars:
                continue
            selected_lines.append(line)
            current_length += len(line) + 1
        lines.extend(reversed(selected_lines))
        return "\n".join(lines)

    def remove(self, key: str):
        self._store.pop(key, None)
        self._save()
