"""Session tools — let the model list, search, and load past sessions."""
from __future__ import annotations

from typing import TYPE_CHECKING

from bytia_kode.tools.registry import Tool, ToolResult

if TYPE_CHECKING:
    from bytia_kode.session import SessionStore


class SessionListTool(Tool):
    name = "session_list"
    description = "List saved sessions. Optionally filter by source ('tui' or 'telegram')."
    parameters = {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "Filter by source: 'tui', 'telegram', or omit for all",
            },
            "limit": {
                "type": "integer",
                "description": "Max sessions to return (default 15)",
                "default": 15,
            },
        },
    }

    def __init__(self, session_store: SessionStore):
        self._store = session_store

    async def execute(self, source: str | None = None, limit: int = 15, **_) -> ToolResult:
        sessions = self._store.list_sessions(source=source, limit=limit)
        if not sessions:
            return ToolResult(output="No sessions found.")
        lines = []
        for s in sessions:
            sid = s.session_id
            title = s.title or "Untitled"
            count = s.message_count
            updated = s.updated_at[:16] if s.updated_at else "?"
            src = s.source
            lines.append(f"  {sid} [{src}] {title} — {count} msgs ({updated})")
        return ToolResult(output="Saved sessions:\n" + "\n".join(lines))


class SessionLoadTool(Tool):
    name = "session_load"
    description = "Load context from a past session into the current conversation."
    parameters = {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "The session ID to load context from",
            },
            "max_messages": {
                "type": "integer",
                "description": "Max messages to include (default 20)",
                "default": 20,
            },
        },
        "required": ["session_id"],
    }

    def __init__(self, session_store: SessionStore):
        self._store = session_store

    async def execute(self, session_id: str, max_messages: int = 20, **_) -> ToolResult:
        context = self._store.get_session_context(session_id, max_messages)
        return ToolResult(output=context)


class SessionSearchTool(Tool):
    name = "session_search"
    description = "Search sessions by title. Returns matching session IDs and metadata."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (matched against session titles)",
            },
            "limit": {
                "type": "integer",
                "description": "Max results (default 10)",
                "default": 10,
            },
        },
        "required": ["query"],
    }

    def __init__(self, session_store: SessionStore):
        self._store = session_store

    async def execute(self, query: str, limit: int = 10, **_) -> ToolResult:
        sessions = self._store.search_sessions(query, limit=limit)
        if not sessions:
            return ToolResult(output=f"No sessions matching '{query}'.")
        lines = []
        for s in sessions:
            lines.append(f"  {s.session_id} [{s.source}] {s.title or 'Untitled'} — {s.message_count} msgs")
        return ToolResult(output=f"Sessions matching '{query}':\n" + "\n".join(lines))
