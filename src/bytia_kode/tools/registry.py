"""Tool registry and base tool definitions."""
from __future__ import annotations

import logging
import logging
import subprocess
import os
from typing import Any, Callable, Awaitable

from pydantic import BaseModel

from bytia_kode.providers.client import ToolDef


logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

class ToolResult(BaseModel):
    output: str
    error: bool = False


class Tool:
    """Base class for all tools."""
    """Base tool definition."""

    name: str = ""
    description: str = ""
    parameters: dict = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not cls.name:
            cls.name = cls.__name__.lower().replace("tool", "")

    def to_tool_def(self) -> ToolDef:
        return ToolDef(function={
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        })

    async def execute(self, **kwargs) -> ToolResult:
        raise NotImplementedError


class BashTool(Tool):
    name = "bash"
    description = "Execute a shell command and return the output"
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to execute"},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 60},
            "workdir": {"type": "string", "description": "Working directory", "default": "."},
        },
        "required": ["command"],
    }

    async def execute(self, command: str, timeout: int = 60, workdir: str = ".", **_) -> ToolResult:
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.path.expanduser(workdir),
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            return ToolResult(output=output[:50000], error=result.returncode != 0)
        except subprocess.TimeoutExpired:
            return ToolResult(output=f"Command timed out after {timeout}s", error=True)
        except Exception as e:
            logger.error(f"Error executing tool: {e}")
            return ToolResult(output=str(e), error=True)


class FileReadTool(Tool):
    name = "file_read"
    description = "Read the contents of a file"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file"},
            "offset": {"type": "integer", "description": "Line to start reading from (1-indexed)", "default": 1},
            "limit": {"type": "integer", "description": "Maximum lines to read", "default": 500},
        },
        "required": ["path"],
    }

    async def execute(self, path: str, offset: int = 1, limit: int = 500, **_) -> ToolResult:
        try:
            p = os.path.expanduser(path)
            with open(p, "r") as f:
                lines = f.readlines()
            selected = lines[offset - 1 : offset - 1 + limit]
            numbered = [f"{offset + i:6d}|{line}" for i, line in enumerate(selected)]
            return ToolResult(output="".join(numbered))
        except FileNotFoundError:
            return ToolResult(output=f"File not found: {path}", error=True)
        except Exception as e:
            logger.error(f"Error executing tool: {e}")
            return ToolResult(output=str(e), error=True)


class FileWriteTool(Tool):
    name = "file_write"
    description = "Write content to a file (overwrites entirely)"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    }

    async def execute(self, path: str, content: str, **_) -> ToolResult:
        try:
            p = os.path.expanduser(path)
            parent = os.path.dirname(p)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(p, "w") as f:
                f.write(content)
            return ToolResult(output=f"Wrote {len(content)} chars to {path}")
        except Exception as e:
            logger.error(f"Error executing tool: {e}")
            return ToolResult(output=str(e), error=True)


class ToolRegistry:
    """
    Registry of available tools.
    Provides methods to register, execute, and list tools.
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._register_defaults()

    def _register_defaults(self):
        for tool_cls in [BashTool, FileReadTool, FileWriteTool]:
            self.register(tool_cls())

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def get_tool_defs(self) -> list[ToolDef]:
        return [t.to_tool_def() for t in self._tools.values()]

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    async def execute(self, tool_name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        if arguments is None:
            arguments = {}
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(output=f"Unknown tool: {tool_name}", error=True)
        return await tool.execute(**arguments)
