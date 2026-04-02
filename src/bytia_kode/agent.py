"""Agentic conversation loop - the brain."""
from __future__ import annotations

import json
import logging
from importlib import resources
from textwrap import dedent
from typing import Any, AsyncIterator

import httpx
import yaml

from bytia_kode.config import AppConfig
from bytia_kode.memory.store import BytMemoryConnector
from bytia_kode.providers.client import Message
from bytia_kode.providers.manager import ProviderManager
from bytia_kode.skills.loader import SkillLoader
from bytia_kode.tools.registry import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)
CORE_IDENTITY_PACKAGE = "bytia_kode.prompts"
CORE_IDENTITY_RESOURCE = "core_identity.yaml"


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
    """
    The agentic loop: think -> act -> observe -> repeat.
    This class manages the conversation history, tools, and provider interactions.
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.providers = ProviderManager(config.provider)
        self.tools = ToolRegistry()
        self.skills = SkillLoader()
        self.memory = BytMemoryConnector(config.data_dir)
        self.messages: list[Message] = []
        self.max_iterations = 50
        self._system_prompt = load_system_prompt()

    def _build_system_prompt(self) -> str:
        parts = [self._system_prompt]
        skill_summary = self.skills.skill_summary()
        if skill_summary:
            parts.append(skill_summary)
        mem_context = self.memory.get_context()
        if mem_context:
            parts.append(mem_context)
        return "\n\n".join(parts)

    async def chat(self, user_message: str, provider: str = "primary") -> AsyncIterator[str]:
        """Process a user message through the agentic loop, yielding text chunks."""
        sanitized_message = _sanitize_user_message(user_message)
        if not sanitized_message:
            yield "Input discarded: empty or non-printable message."
            return

        self.messages.append(Message(role="user", content=sanitized_message))

        provider_client = self.providers.get(provider)
        tool_defs = self.tools.get_tool_defs()

        try:
            for _iteration in range(self.max_iterations):
                all_messages = [Message(role="system", content=self._build_system_prompt())] + self.messages

                response = await provider_client.chat(
                    messages=all_messages,
                    tools=tool_defs if tool_defs else None,
                )

                self.messages.append(Message(
                    role="assistant",
                    content=response.content,
                    tool_calls=[tc.model_dump() for tc in response.tool_calls] if response.tool_calls else None,
                ))

                if not response.tool_calls:
                    if response.content:
                        yield response.content
                    break

                if response.content:
                    yield response.content

                for tool_call in response.tool_calls:
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
                    result: ToolResult = await self.tools.execute(tool_name, arguments)

                    self.messages.append(Message(
                        role="tool",
                        content=result.output,
                        tool_call_id=tool_call.id,
                        name=tool_name,
                    ))
            else:
                yield "\n[Max iterations reached]"
        except (TimeoutError, ConnectionError, RuntimeError, httpx.HTTPError) as exc:
            error_message = _format_chat_error(exc)
            logger.error("Agent chat failure: %s", error_message)
            self.messages.append(Message(role="assistant", content=error_message))
            yield error_message

    async def chat_stream(self, user_message: str, provider: str = "primary") -> AsyncIterator[str]:
        """Stream response for non-tool-use conversations."""
        sanitized_message = _sanitize_user_message(user_message)
        if not sanitized_message:
            yield "Input discarded: empty or non-printable message."
            return

        self.messages.append(Message(role="user", content=sanitized_message))
        all_messages = [Message(role="system", content=self._build_system_prompt())] + self.messages

        provider_client = self.providers.get(provider)

        full_response = ""
        async for chunk in provider_client.chat_stream(messages=all_messages):
            full_response += chunk
            yield chunk

        if full_response:
            self.messages.append(Message(role="assistant", content=full_response))

    def reset(self):
        """Clear conversation history."""
        self.messages.clear()

    async def close(self):
        await self.providers.close_all()
