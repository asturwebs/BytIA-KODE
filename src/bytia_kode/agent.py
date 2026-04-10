"""Agentic conversation loop - the brain."""
from __future__ import annotations

import json
import logging
from importlib import resources
from pathlib import Path
from textwrap import dedent
from typing import Any, AsyncIterator

import httpx
import yaml

from bytia_kode.config import AppConfig
from bytia_kode.providers.client import Message
from bytia_kode.providers.manager import ProviderManager
from bytia_kode.session import SessionStore
from bytia_kode.skills.loader import SkillLoader
from bytia_kode.tools.registry import ToolRegistry, ToolResult
from bytia_kode.tools.session import SessionListTool, SessionLoadTool, SessionSearchTool

logger = logging.getLogger(__name__)
CORE_IDENTITY_PACKAGE = "bytia_kode.prompts"
CORE_IDENTITY_RESOURCE = "core_identity.yaml"
MAX_CONTEXT_TOKENS = 131072  # ~128k tokens default (Gemma 4 26B supports 256k)


def load_identity() -> dict[str, Any]:
    try:
        resource = resources.files(CORE_IDENTITY_PACKAGE).joinpath(CORE_IDENTITY_RESOURCE)
        with resource.open("rb") as fh:
            payload = yaml.safe_load(fh)
        logger.info("Identity loaded from package resource")
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            f"Core identity resource not found: {CORE_IDENTITY_PACKAGE}/{CORE_IDENTITY_RESOURCE}"
        ) from exc
    except yaml.YAMLError as exc:
        raise RuntimeError(
            f"Core identity resource is invalid YAML: {CORE_IDENTITY_PACKAGE}/{CORE_IDENTITY_RESOURCE}"
        ) from exc

    if not isinstance(payload, dict) or not payload:
        raise RuntimeError(
            f"Core identity resource must contain a non-empty mapping: {CORE_IDENTITY_PACKAGE}/{CORE_IDENTITY_RESOURCE}"
        )
    return payload


def load_system_prompt() -> str:
    payload = load_identity()
    rendered_yaml = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False).strip()
    return dedent(
        f"""
        BytIA Core Identity
        ===================
        Treat every field below as binding constitutional system-level instruction.

        {rendered_yaml}
        """
    ).strip()


def _sanitize_user_message(user_message: str) -> str:
    filtered = "".join(ch for ch in user_message if ch.isprintable() or ch in "\n\t")
    lines = [line.rstrip() for line in filtered.splitlines()]
    sanitized = "\n".join(lines).strip()
    return sanitized


def _format_chat_error(exc: Exception) -> str:
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return f"Provider timeout: {exc}"
    if isinstance(exc, (ConnectionError, httpx.ConnectError, httpx.NetworkError)):
        return f"Provider connection error: {exc}"
    if isinstance(exc, httpx.HTTPError):
        return f"Provider HTTP error: {exc}"
    if isinstance(exc, RuntimeError):
        return f"Provider runtime error: {exc}"
    return f"Unexpected provider error: {exc}"


class Agent:
    """The agentic loop: think -> act -> observe -> repeat."""

    def __init__(self, config: AppConfig, session_store: SessionStore | None = None):
        self.config = config
        self.providers = ProviderManager(config.provider)
        self.tools = ToolRegistry()

        from bytia_kode.tools.registry import set_trusted_paths
        set_trusted_paths([config.data_dir])

        self.skills = SkillLoader(skill_dirs=[config.skills_dir])
        self.skills.load_all()
        self.messages: list[Message] = []
        self.max_iterations = 50
        self._max_context_tokens = MAX_CONTEXT_TOKENS
        self._system_prompt = load_system_prompt()
        self._bkode_path, self._bkode_content = self._load_bkode()
        self._initialized = False
        self.on_tool_call: list = []  # callbacks: fn(tool_name: str)
        self.on_tool_done: list = []  # callbacks: fn(tool_name: str, output: str, error: bool)

        # Session persistence
        self._session_store = session_store or SessionStore(config.data_dir / "sessions.db")
        self._current_session_id: str | None = None

        # Register session tools (need store reference)
        self.tools.register(SessionListTool(self._session_store))
        self.tools.register(SessionLoadTool(self._session_store))
        self.tools.register(SessionSearchTool(self._session_store))

    def update_context_limit(self, ctx_size: int) -> None:
        """Update max context tokens from router info (dynamic ctx_size)."""
        if ctx_size > 0:
            self._max_context_tokens = ctx_size

    def _load_bkode(self) -> tuple[Path | None, str]:
        """Walk up from CWD looking for B-KODE.md (like CLAUDE.md, HERMES.md)."""
        cwd = Path.cwd().resolve()
        for candidate in (cwd, *cwd.parents):
            bk = candidate / "B-KODE.md"
            if bk.is_file():
                try:
                    content = bk.read_text(encoding="utf-8").strip()
                    if content:
                        logger.info("B-KODE.md loaded from %s", bk)
                        return bk, content
                except OSError as exc:
                    logger.warning("Failed to read B-KODE.md at %s: %s", bk, exc)
            if candidate == candidate.parent:
                break
        return None, ""

    def _build_system_prompt(self) -> str:
        parts = [self._system_prompt]
        if self._bkode_content:
            parts.append(f"# Project Instructions (B-KODE.md)\n\n{self._bkode_content}")
        skill_summary = self.skills.skill_summary()
        if skill_summary:
            parts.append(skill_summary)
        session_context = self._get_previous_session_summary()
        if session_context:
            parts.append(session_context)
        return "\n\n".join(parts)

    def _get_previous_session_summary(self, source: str | None = None) -> str:
        """Build a compact summary of the most recent past session for context continuity.

        Uses last 3 messages (truncated) — lightweight, deterministic, no LLM call needed.
        The model can use session_load to retrieve full context if needed.
        """
        if self._current_session_id:
            source_filter = self._current_session_id.split("_")[0] if "_" in self._current_session_id else source
        else:
            source_filter = source or "tui"
        sessions = self._session_store.list_sessions(source=source_filter, limit=5)
        previous = [s for s in sessions if s.session_id != self._current_session_id]
        if not previous:
            return ""
        latest = previous[0]
        messages = self._session_store.load_messages(latest.session_id)
        if not messages:
            return ""
        lines = [
            f"# Previous Session Context",
            f"Session: {latest.session_id} | Source: {latest.source}",
            f"Title: {latest.title or '(untitled)'} | Updated: {latest.updated_at[:16] if latest.updated_at else '?'}",
            f"Messages: {latest.message_count}",
            "",
            "Recent messages (last 3):",
        ]
        for msg in messages[-3:]:
            role = msg["role"].upper()
            content = (msg.get("content") or "")[:200]
            lines.append(f"  [{role}] {content}")
        lines.append("")
        lines.append("Use session_load to retrieve full context from this or other past sessions.")
        return "\n".join(lines)

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token estimate: chars / 3 for mixed EN/ES content."""
        return len(text) // 3

    def _estimate_tokens(self) -> int:
        total = len(self._build_system_prompt())
        for m in self.messages:
            if m.content:
                total += len(m.content)
            if m.tool_calls:
                total += sum(len(str(tc)) for tc in m.tool_calls)
        return total // 3

    async def _manage_context(self, provider_client) -> None:
        """Compress old messages when context exceeds 75% of max.

        Strategy:
        1. If dynamic ctx_size available from router, use it; else use _max_context_tokens.
        2. When threshold exceeded, summarize oldest messages using the model itself.
        3. System messages are never summarized.
        4. Fallback to truncation if summarization fails.
        """
        threshold = int(self._max_context_tokens * 0.75)
        while self._estimate_tokens() > threshold and len(self.messages) > 4:
            candidates = [m for m in self.messages if m.role != "system"]
            if len(candidates) < 2:
                break

            old = candidates[:2]
            summary = await self._summarize_messages(old, provider_client)
            summary_msg = Message(
                role="system",
                content=f"[Previous conversation summarized] {summary}",
            )

            old_indices = []
            for msg in old:
                try:
                    old_indices.append(self.messages.index(msg))
                except ValueError:
                    continue

            for idx in sorted(old_indices, reverse=True):
                self.messages.pop(idx)

            self.messages.insert(0, summary_msg)

    async def _summarize_messages(self, messages: list[Message], provider_client) -> str:
        """Ask the model to summarize a list of messages. Fallback to truncation."""
        conversation_text = "\n".join(
            f"{m.role}: {m.content}" for m in messages if m.content
        )
        prompt = (
            "Resume el siguiente fragmento de conversación en 2-3 frases. "
            "Preserva hechos clave, decisiones y contexto importante. "
            "Responde SOLO con el resumen, nada más.\n\n"
            f"{conversation_text}"
        )
        try:
            response = await provider_client.chat(
                messages=[Message(role="user", content=prompt)],
                temperature=0.0,
                max_tokens=256,
            )
            if response.content:
                return response.content.strip()
        except Exception as exc:
            logger.warning("Summarization failed, falling back to truncation: %s", exc)

        fallback = " | ".join(
            f"{m.role[:3].upper()}: {m.content[:80]}..." for m in messages if m.content
        )
        return fallback

    async def _handle_tool_calls(self, tool_calls) -> None:
        for tool_call in tool_calls:
            fn = tool_call.function if isinstance(tool_call.function, dict) else {}
            tool_name = fn.get("name")
            raw_arguments = fn.get("arguments", {})
            arguments = raw_arguments
            if isinstance(raw_arguments, str):
                try:
                    arguments = json.loads(raw_arguments)
                except json.JSONDecodeError:
                    logger.error("Failed to decode JSON arguments: %s", raw_arguments)
                    arguments = {}

            if not isinstance(arguments, dict):
                arguments = {}

            if not tool_name:
                self.messages.append(Message(
                    role="tool",
                    content="Invalid tool call: missing function name",
                    tool_call_id=tool_call.id,
                    name="invalid_tool",
                ))
                continue

            logger.info("Tool call: %s(%s)", tool_name, arguments)
            for cb in self.on_tool_call:
                cb(tool_name)
            result: ToolResult = await self.tools.execute(tool_name, arguments)
            for cb in self.on_tool_done:
                cb(tool_name, result.output, result.error)
            self.messages.append(Message(
                role="tool",
                content=result.output,
                tool_call_id=tool_call.id,
                name=tool_name,
            ))
            # Auto-save tool results
            if self._current_session_id:
                self._session_store.append_message(
                    self._current_session_id,
                    role="tool", content=result.output or "",
                    tool_call_id=tool_call.id, name=tool_name,
                )

    async def chat(self, user_message: str, provider: str = "primary") -> AsyncIterator[str | tuple[str, str]]:
        """Process a user message through the agentic loop, streaming text and reasoning chunks.

        Yields:
          str               — text content chunk
          ("reasoning", str) — reasoning/thinking chunk
        """
        if not self._initialized:
            detected = await self.providers.auto_detect_model()
            self._initialized = True
            if not detected:
                yield "No hay ningún modelo cargado en el router. Carga uno primero (routeron + UI en :8080/slots)."
                return

        sanitized_message = _sanitize_user_message(user_message)
        if not sanitized_message:
            yield "Input discarded: empty or non-printable message."
            return

        self.messages.append(Message(role="user", content=sanitized_message))
        provider_client = self.providers.get(provider)
        tool_defs = self.tools.get_tool_defs()
        await self._manage_context(provider_client)

        try:
            for _iteration in range(self.max_iterations):
                all_messages = [Message(role="system", content=self._build_system_prompt())] + self.messages
                response_text = ""
                tool_calls_accum: list = []

                async for chunk_type, data in provider_client.chat_stream(
                    messages=all_messages,
                    tools=tool_defs if tool_defs else None,
                ):
                    if chunk_type == "text" and isinstance(data, str):
                        response_text += data
                        yield data
                    elif chunk_type == "reasoning" and isinstance(data, str):
                        yield ("reasoning", data)
                    elif chunk_type == "tool_calls" and isinstance(data, list):
                        tool_calls_accum = data

                msg_count_before = len(self.messages)
                self.messages.append(Message(
                    role="assistant",
                    content=response_text or "[razonamiento sin respuesta de texto]",
                    tool_calls=[tc.model_dump() for tc in tool_calls_accum] if tool_calls_accum else None,
                ))

                # Auto-save: append user message + assistant response
                if self._current_session_id:
                    self._session_store.append_message(
                        self._current_session_id,
                        role="user", content=sanitized_message,
                    )
                    self._session_store.append_message(
                        self._current_session_id,
                        role="assistant", content=response_text or "",
                        tool_calls=[tc.model_dump() for tc in tool_calls_accum] if tool_calls_accum else None,
                    )
                    # Auto-title from first user message
                    if msg_count_before == 0 and sanitized_message:
                        self._session_store.update_title(
                            self._current_session_id, sanitized_message[:80],
                        )

                if not tool_calls_accum:
                    break

                await self._handle_tool_calls(tool_calls_accum)
            else:
                yield "\n[Max iterations reached]"
        except (TimeoutError, ConnectionError, RuntimeError, httpx.HTTPError) as exc:
            error_message = _format_chat_error(exc)
            logger.error("Agent chat failure: %s", error_message)
            self.messages.append(Message(role="assistant", content=f"[Error: {error_message}]"))
            if self._current_session_id:
                self._session_store.append_message(
                    self._current_session_id, role="assistant", content=f"[Error: {error_message}]",
                )
            yield ("error", error_message)

    def set_session(self, source: str = "tui", source_ref: str = "") -> str:
        """Set the current session. Creates or resumes if exists."""
        session_id = f"{source}_{source_ref}" if source_ref else self._session_store.create_session(source, source_ref)
        if self._session_store.get_metadata(session_id):
            self.messages = self._load_messages_from_store(session_id)
        else:
            session_id = self._session_store.create_session(source, source_ref)
        self._current_session_id = session_id
        logger.info("Session set: %s", session_id)
        return session_id

    def load_session_by_id(self, session_id: str) -> bool:
        """Load a specific session by ID, replacing current messages."""
        messages = self._session_store.load_messages(session_id)
        if not messages:
            logger.warning("Session not found: %s", session_id)
            return False
        self._current_session_id = session_id
        self.messages: list[Message] = messages  # type: ignore[assignment]
        logger.info("Session loaded: %s (%d messages)", session_id, len(messages))
        return True

    def save_current_session(self) -> bool:
        """Save current messages to the active session."""
        if not self._current_session_id:
            return False
        for msg in self.messages:
            self._session_store.append_message(
                self._current_session_id,
                msg.role, msg.content,
                msg.tool_calls, msg.tool_call_id, msg.name,
            )
        logger.debug("Session saved: %s", self._current_session_id)
        return True

    def list_sessions(self, source: str | None = None, limit: int = 20) -> list[dict]:
        """List available sessions, optionally filtered by source."""
        metas = self._session_store.list_sessions(source=source, limit=limit)
        return [m.to_dict() for m in metas]

    def get_session_context(self, session_id: str, max_messages: int = 20) -> str:
        """Get formatted context from another session for model consumption."""
        return self._session_store.get_session_context(session_id, max_messages)

    def _load_messages_from_store(self, session_id: str) -> list[Message]:
        """Convert stored dicts back to Message objects."""
        """Convert stored dicts back to Message objects."""
        rows = self._session_store.load_messages(session_id)
        messages = []
        for row in rows:
            messages.append(Message(
                role=row["role"],
                content=row.get("content"),
                tool_calls=row.get("tool_calls"),
                tool_call_id=row.get("tool_call_id"),
                name=row.get("name"),
            ))
        return messages

    def reset(self):
        """Clear conversation history. Note: does NOT delete the session from disk."""
        self.messages.clear()
        self._current_session_id = None

    async def close(self):
        await self.providers.close_all()
