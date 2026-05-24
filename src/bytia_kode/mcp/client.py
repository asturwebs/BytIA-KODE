from __future__ import annotations

import asyncio
import logging
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from bytia_kode.mcp.config import McpServerConfig

logger = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 10.0
_MAX_OUTPUT_CHARS = 50_000


@dataclass
class McpToolDef:
    name: str
    description: str
    input_schema: dict


class McpConnectionError(Exception):
    pass


class McpToolError(Exception):
    pass


class McpToolTimeout(McpToolError):
    pass


class McpClient:
    def __init__(self, config: McpServerConfig) -> None:
        self._config = config
        self._exit_stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self._session is not None

    @property
    def server_name(self) -> str:
        return self._config.name

    async def connect(self) -> None:
        server_params = StdioServerParameters(
            command=self._config.command,
            args=self._config.args,
            env=self._build_env(),
            cwd=self._config.cwd,
        )

        try:
            self._exit_stack = AsyncExitStack()
            await asyncio.wait_for(
                self._exit_stack.__aenter__(), timeout=_CONNECT_TIMEOUT
            )

            read_stream, write_stream = await self._exit_stack.enter_async_context(
                stdio_client(server_params)
            )

            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )

            await self._session.initialize()
            self._connected = True
            logger.info("MCP server '%s' connected", self._config.name)

        except asyncio.TimeoutError:
            await self._cleanup()
            raise McpConnectionError(
                f"Timeout connecting to MCP server '{self._config.name}'"
            )
        except Exception as exc:
            await self._cleanup()
            raise McpConnectionError(
                f"Failed to connect to MCP server '{self._config.name}': {exc}"
            ) from exc

    def _build_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.update(self._config.env)
        return env

    async def list_tools(self) -> list[McpToolDef]:
        if not self.is_connected:
            return []
        result = await self._session.list_tools()
        return [
            McpToolDef(
                name=t.name,
                description=t.description or "",
                input_schema=t.inputSchema,
            )
            for t in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict) -> str:
        if not self.is_connected:
            raise McpToolError(f"Server '{self._config.name}' is not connected")
        try:
            result = await asyncio.wait_for(
                self._session.call_tool(name, arguments),
                timeout=self._config.timeout,
            )
        except asyncio.TimeoutError:
            raise McpToolTimeout(
                f"Tool '{name}' on server '{self._config.name}' timed out "
                f"after {self._config.timeout}s"
            )

        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            else:
                parts.append(str(block))

        output = "\n".join(parts)
        if len(output) > _MAX_OUTPUT_CHARS:
            output = output[:_MAX_OUTPUT_CHARS] + "\n... (truncated)"
        return output

    async def disconnect(self) -> None:
        await self._cleanup()
        logger.info("MCP server '%s' disconnected", self._config.name)

    async def _cleanup(self) -> None:
        self._connected = False
        self._session = None
        if self._exit_stack is not None:
            try:
                await self._exit_stack.aclose()
            except Exception:
                pass
            self._exit_stack = None
