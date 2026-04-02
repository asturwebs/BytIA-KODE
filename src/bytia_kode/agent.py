"""Agentic conversation loop - the brain."""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from bytia_kode.config import AppConfig
from bytia_kode.providers.manager import ProviderManager
from bytia_kode.providers.client import Message, ToolDef, ProviderResponse
from bytia_kode.tools.registry import ToolRegistry, ToolResult
from bytia_kode.skills.loader import SkillLoader
from bytia_kode.memory.store import BytMemoryConnector

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are BytIA KODE, an agentic coding assistant. You have access to tools to help the user.

When using tools:
- Read files fully before modifying them
- Execute commands when asked
- Be direct and concise
- If something fails, diagnose and retry

Always respond in the same language as the user.
"""


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
        self._system_prompt = SYSTEM_PROMPT

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
        self.messages.append(Message(role="user", content=user_message))

        provider_client = self.providers.get(provider)
        tool_defs = self.tools.get_tool_defs()

        for iteration in range(self.max_iterations):
            # Build message list with system prompt
            all_messages = [Message(role="system", content=self._build_system_prompt())] + self.messages

            # Call LLM
            response = await provider_client.chat(
                messages=all_messages,
                tools=tool_defs if tool_defs else None,
            )

            # Add assistant message to history
            self.messages.append(Message(
                role="assistant",
                content=response.content,
                tool_calls=[tc.model_dump() for tc in response.tool_calls] if response.tool_calls else None,
            ))

            # If no tool calls, we're done -- yield the text
            if not response.tool_calls:
                if response.content:
                    yield response.content
                break

            if response.content:
                yield response.content

            # Execute tool calls
            for tool_call in response.tool_calls:
                fn = tool_call.function if isinstance(tool_call.function, dict) else {}
                tool_name = fn.get("name")
                raw_arguments = fn.get("arguments", {})
                arguments = raw_arguments
                if isinstance(raw_arguments, str):
                    try:
                        arguments = json.loads(raw_arguments)
                    except json.JSONDecodeError:
                        logger.error(f"Failed to decode JSON arguments: {raw_arguments}")
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

                logger.info(f"Tool call: {tool_name}({arguments})")
                result: ToolResult = await self.tools.execute(tool_name, arguments)

                self.messages.append(Message(
                    role="tool",
                    content=result.output,
                    tool_call_id=tool_call.id,
                    name=tool_name,
                ))

        else:
            yield "\n[Max iterations reached]"

    async def chat_stream(self, user_message: str, provider: str = "primary") -> AsyncIterator[str]:
        """Stream response for non-tool-use conversations."""
        self.messages.append(Message(role="user", content=user_message))
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
