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
from bytia_kode.skills.loader import SkillLoader
from bytia_kode.tools.registry import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)
CORE_IDENTITY_PACKAGE = "bytia_kode.prompts"
CORE_IDENTITY_RESOURCE = "core_identity.yaml"
MAX_CONTEXT_TOKENS = 16384  # ~16k tokens default


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

    def __init__(self, config: AppConfig):
        self.config = config
        self.providers = ProviderManager(config.provider)
        self.tools = ToolRegistry()
        self.skills = SkillLoader(skill_dirs=[config.skills_dir])
        self.skills.load_all()
        self.messages: list[Message] = []
        self.max_iterations = 50
        self._max_context_tokens = MAX_CONTEXT_TOKENS
        self._system_prompt = load_system_prompt()
        self._bkode_path, self._bkode_content = self._load_bkode()
        self._initialized = False
        self.on_tool_call: list = []  # callbacks: fn(tool_name: str)
        self.on_tool_done: list = []  # callbacks: fn(tool_name: str, output: str)

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
        return "\n\n".join(parts)

    def _estimate_tokens(self) -> int:
        """Rough token estimate: chars / 3.5 for mixed content."""
        total = len(self._build_system_prompt())
        for m in self.messages:
            if m.content:
                total += len(m.content)
            if m.tool_calls:
                total += sum(len(str(tc)) for tc in m.tool_calls)
        return total // 3

    def _manage_context(self) -> None:
        """Compress old messages when context exceeds 75% of max."""
        threshold = int(MAX_CONTEXT_TOKENS * 0.75)
        while self._estimate_tokens() > threshold and len(self.messages) > 4:
            old = self.messages[:2]
            summary_text = " | ".join(
                f"{m.role[:3].upper()}: {m.content[:80]}..." for m in old
            )
            summary_msg = Message(
                role="system",
                content=f"[Previous conversation summarized] {summary_text}",
            )
            self.messages = [summary_msg] + self.messages[len(old):]

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
                cb(tool_name, result.output)
            self.messages.append(Message(
                role="tool",
                content=result.output,
                tool_call_id=tool_call.id,
                name=tool_name,
            ))

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
        self._manage_context()

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

                self.messages.append(Message(
                    role="assistant",
                    content=response_text or None,
                    tool_calls=[tc.model_dump() for tc in tool_calls_accum] if tool_calls_accum else None,
                ))

                if not tool_calls_accum:
                    break

                await self._handle_tool_calls(tool_calls_accum)
            else:
                yield "\n[Max iterations reached]"
        except (TimeoutError, ConnectionError, RuntimeError, httpx.HTTPError) as exc:
            error_message = _format_chat_error(exc)
            logger.error("Agent chat failure: %s", error_message)
            yield error_message

    def reset(self):
        """Clear conversation history."""
        self.messages.clear()

    async def close(self):
        await self.providers.close_all()
