"""Tool registry and base tool definitions."""
from __future__ import annotations

import asyncio
import logging
import re
import shlex
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from bytia_kode.providers.client import ToolDef

logger = logging.getLogger(__name__)
_ALLOWED_BINARIES = {"ls", "pwd", "cat", "echo", "git", "grep", "find", "mkdir", "touch", "uv", "python", "python3", "wsl"}


class ToolResult(BaseModel):
    output: str
    error: bool = False


class Tool:
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


def _resolve_workspace_path(path: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    resolved = candidate.resolve()
    workspace = Path.cwd().resolve()
    if workspace == resolved or workspace in resolved.parents:
        return resolved
    raise PermissionError(f"Security violation: path escapes workspace: {path}")


def _read_file_lines(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as fh:
        return fh.readlines()


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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
            argv = shlex.split(command)
            if not argv:
                return ToolResult(output="Security policy: empty command is not allowed", error=True)

            command_base = Path(argv[0]).name
            if command_base not in _ALLOWED_BINARIES:
                return ToolResult(
                    output=f"Security policy violation: command '{command_base}' is not allowed",
                    error=True,
                )

            process = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(_resolve_workspace_path(workdir)),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            output = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")
            if stderr_text:
                output += f"\nSTDERR:\n{stderr_text}"
            return ToolResult(output=output[:50000], error=process.returncode != 0)
        except asyncio.TimeoutError:
            return ToolResult(output=f"Command timed out after {timeout}s", error=True)
        except PermissionError as exc:
            return ToolResult(output=str(exc), error=True)
        except ValueError as exc:
            return ToolResult(output=f"Invalid command syntax: {exc}", error=True)
        except Exception as exc:
            logger.error("Error executing tool: %s", exc)
            return ToolResult(output=str(exc), error=True)


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
            resolved = _resolve_workspace_path(path)
            lines = await asyncio.to_thread(_read_file_lines, resolved)
            selected = lines[offset - 1: offset - 1 + limit]
            numbered = [f"{offset + i:6d}|{line}" for i, line in enumerate(selected)]
            return ToolResult(output="".join(numbered))
        except FileNotFoundError:
            return ToolResult(output=f"File not found: {path}", error=True)
        except PermissionError as exc:
            return ToolResult(output=str(exc), error=True)
        except Exception as exc:
            logger.error("Error executing tool: %s", exc)
            return ToolResult(output=str(exc), error=True)


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
            resolved = _resolve_workspace_path(path)
            await asyncio.to_thread(_write_file, resolved, content)
            return ToolResult(output=f"Wrote {len(content)} chars to {path}")
        except PermissionError as exc:
            return ToolResult(output=str(exc), error=True)
        except Exception as exc:
            logger.error("Error executing tool: %s", exc)
            return ToolResult(output=str(exc), error=True)


_STRIP_TAGS_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_STRIP_TAG_RE = re.compile(r"<[^>]+>")
_MAX_CONTENT_LENGTH = 30000


class WebFetchTool(Tool):
    name = "web_fetch"
    description = "Fetch content from a URL and return it as text. Use for reading web pages, documentation, and APIs."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to fetch"},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 15},
            "max_length": {"type": "integer", "description": "Max content length in chars", "default": 30000},
        },
        "required": ["url"],
    }

    async def execute(self, url: str, timeout: int = 15, max_length: int = _MAX_CONTENT_LENGTH, **_) -> ToolResult:
        if not url.startswith(("http://", "https://")):
            return ToolResult(output="Invalid URL: must start with http:// or https://", error=True)
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                headers={"User-Agent": "BytIA-KODE/0.4 (agentic TUI)"},
                timeout=httpx.Timeout(timeout),
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                if "text/html" in content_type:
                    text = resp.text
                    text = _STRIP_TAGS_RE.sub("", text)
                    text = _STRIP_TAG_RE.sub("", text)
                    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
                elif any(t in content_type for t in ("json", "text/plain", "text/markdown", "text/yaml", "text/xml")):
                    text = resp.text
                else:
                    return ToolResult(
                        output=f"Unsupported content type: {content_type}",
                        error=True,
                    )
                if len(text) > max_length:
                    text = text[:max_length] + f"\n... [truncated at {max_length} chars]"
                return ToolResult(output=text)
        except httpx.HTTPStatusError as exc:
            return ToolResult(output=f"HTTP error {exc.response.status_code}: {exc}", error=True)
        except httpx.TimeoutException:
            return ToolResult(output=f"Request timed out after {timeout}s", error=True)
        except Exception as exc:
            logger.error("web_fetch error: %s", exc)
            return ToolResult(output=f"Fetch failed: {exc}", error=True)


class ToolRegistry:
    """Registry of available tools."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._register_defaults()

    def _register_defaults(self):
        for tool_cls in [BashTool, FileReadTool, FileWriteTool, WebFetchTool]:
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
