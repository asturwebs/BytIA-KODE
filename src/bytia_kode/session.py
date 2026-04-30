"""Session persistence for BytIA-KODE — SQLite WAL storage.

Provides cross-platform session access between TUI and Telegram interfaces.
All writes are append-only INSERT for O(1) performance.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Schema ───────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_ref TEXT DEFAULT '',
    title TEXT DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT (datetime('now')),
    updated_at TIMESTAMP NOT NULL DEFAULT (datetime('now')),
    message_count INTEGER NOT NULL DEFAULT 0,
    token_count INTEGER NOT NULL DEFAULT 0,
    model TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_sessions_source ON sessions(source);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_source_ref ON sessions(source, source_ref);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    seq_num INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT DEFAULT '',
    tool_calls TEXT DEFAULT NULL,
    tool_call_id TEXT DEFAULT NULL,
    name TEXT DEFAULT NULL,
    reasoning_content TEXT DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, seq_num);
"""


class SessionMetadata:
    """Lightweight session metadata, no Pydantic dependency."""
    __slots__ = (
        "session_id", "source", "source_ref", "title",
        "created_at", "updated_at", "message_count", "token_count",
        "model", "is_active",
    )

    def __init__(
        self,
        session_id: str,
        source: str = "tui",
        source_ref: str = "",
        title: str = "",
        created_at: str = "",
        updated_at: str = "",
        message_count: int = 0,
        token_count: int = 0,
        model: str = "",
        is_active: bool = True,
    ):
        self.session_id = session_id
        self.source = source
        self.source_ref = source_ref
        self.title = title
        self.created_at = created_at
        self.updated_at = updated_at
        self.message_count = message_count
        self.token_count = token_count
        self.model = model
        self.is_active = is_active

    @classmethod
    def from_row(cls, row: tuple) -> SessionMetadata:
        return cls(
            session_id=row[0], source=row[1], source_ref=row[2],
            title=row[3], created_at=row[4], updated_at=row[5],
            message_count=row[6], token_count=row[7], model=row[8],
            is_active=bool(row[9]),
        )

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id, "source": self.source,
            "source_ref": self.source_ref, "title": self.title,
            "created_at": self.created_at, "updated_at": self.updated_at,
            "message_count": self.message_count, "token_count": self.token_count,
            "model": self.model, "is_active": self.is_active,
        }


class SessionStore:
    """SQLite WAL-backed session store. Thread-safe via connection-per-method."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """Open a fresh connection (no thread sharing)."""
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            try:
                conn.execute("ALTER TABLE messages ADD COLUMN reasoning_content TEXT DEFAULT NULL")
            except Exception:
                pass

    # ── Session Lifecycle ────────────────────────────────────────────────────────

    def create_session(
        self, source: str = "tui", source_ref: str = "", title: str = ""
    ) -> str:
        """Create a new session and return its ID."""
        import uuid
        session_id = f"{source}_{uuid.uuid4().hex[:8]}"
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, source, source_ref, title) VALUES (?, ?, ?, ?)",
                (session_id, source, source_ref, title),
            )
        logger.debug("Session created: %s (%s/%s)", session_id, source, source_ref)
        return session_id

    def append_message(
        self, session_id: str, role: str, content: str | None = None,
        tool_calls: list[dict] | None = None, tool_call_id: str | None = None,
        name: str | None = None, reasoning_content: str | None = None,
    ) -> None:
        """Append a message to a session. Atomic: INSERT + UPDATE metadata in one transaction.

        O(1) — only INSERT, no history rewrite.
        """
        tc_json = json.dumps(tool_calls) if tool_calls else None
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO messages
                       (session_id, seq_num, role, content, tool_calls, tool_call_id, name, reasoning_content)
                       VALUES (
                           ?,
                           COALESCE((SELECT MAX(seq_num) FROM messages WHERE session_id = ?), 0) + 1,
                           ?, ?, ?, ?, ?, ?
                       )""",
                    (session_id, session_id, role, content, tc_json, tool_call_id, name, reasoning_content),
                )
                conn.execute(
                    """UPDATE sessions
                       SET message_count = message_count + 1,
                           updated_at = CURRENT_TIMESTAMP
                       WHERE session_id = ?""",
                    (session_id,),
                )
        except Exception as e:
            logger.error("Failed to append message to session %s: %s", session_id, e)

    def cleanup_empty_sessions(self, max_age_hours: int = 24) -> int:
        """Delete sessions with zero messages older than max_age_hours. Returns count deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                """DELETE FROM sessions
                   WHERE message_count = 0
                   AND created_at < datetime('now', ?)""",
                (f"-{max_age_hours} hours",),
            )
        deleted = cursor.rowcount
        if deleted:
            logger.info("Cleaned up %d empty sessions", deleted)
        return deleted

    def load_messages(self, session_id: str) -> list[dict]:
        """Load all messages from a session, ordered by seq_num."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content, tool_calls, tool_call_id, name, reasoning_content "
                "FROM messages WHERE session_id = ? ORDER BY seq_num",
                (session_id,),
            ).fetchall()
        messages = []
        for row in rows:
            msg = {"role": row[0], "content": row[1]}
            if row[2]:
                try:
                    msg["tool_calls"] = json.loads(row[2])
                except (json.JSONDecodeError, TypeError):
                    msg["tool_calls"] = None
            if row[3]:
                msg["tool_call_id"] = row[3]
            if row[4]:
                msg["name"] = row[4]
            if row[5]:
                msg["reasoning_content"] = row[5]
            messages.append(msg)
        return messages

    def get_metadata(self, session_id: str) -> SessionMetadata | None:
        """Get metadata for a single session."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        if not row:
            return None
        return SessionMetadata.from_row(row)

    def list_sessions(
        self, source: str | None = None, limit: int = 20, offset: int = 0,
    ) -> list[SessionMetadata]:
        """List sessions, optionally filtered by source. Most recent first."""
        with self._connect() as conn:
            if source:
                rows = conn.execute(
                    "SELECT * FROM sessions "
                    "WHERE source = ? AND is_active = 1 "
                    "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (source, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE is_active = 1 "
                    "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
        return [SessionMetadata.from_row(r) for r in rows]

    def search_sessions(self, query: str, limit: int = 10) -> list[SessionMetadata]:
        """Search sessions by title (simple LIKE match)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE title LIKE ? AND is_active = 1 "
                "ORDER BY updated_at DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
        return [SessionMetadata.from_row(r) for r in rows]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages (CASCADE)."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE session_id = ?", (session_id,)
            )
            return cursor.rowcount > 0

    def get_session_context(
        self, session_id: str, max_messages: int = 20,
    ) -> str:
        """Get formatted context from a session for model consumption."""
        messages = self.load_messages(session_id)
        if not messages:
            return f"Session not found: {session_id}"
        meta = self.get_metadata(session_id)
        header = f"Session: {session_id}"
        if meta:
            header += f" | Source: {meta.source}"
            if meta.title:
                header += f" | Title: {meta.title}"
        parts = [header, ""]
        for msg in messages[-max_messages:]:
            role = msg["role"].upper()
            content = (msg.get("content") or "")[:500]
            parts.append(f"[{role}] {content}")
        return "\n".join(parts)

    def update_title(self, session_id: str, title: str) -> bool:
        """Update session title (auto-generated from first message)."""
        if not title:
            return False
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET title = ? WHERE session_id = ? AND (title = '' OR title IS NULL)",
                (title[:80], session_id),
            )
            return True

    def update_metadata(self, session_id: str, **kwargs) -> None:
        """Update session metadata fields (model, token_count)."""
        allowed = {"model", "token_count"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [session_id]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE sessions SET {set_clause} WHERE session_id = ?",
                values,
            )
