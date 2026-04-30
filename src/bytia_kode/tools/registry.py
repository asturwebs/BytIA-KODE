"""Tool registry and base tool definitions."""
from __future__ import annotations

import asyncio
import difflib
import logging
import re
import shlex
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from bytia_kode.providers.client import ToolDef

logger = logging.getLogger(__name__)

_TRUSTED_PATHS: list[Path] = []
_WORKSPACE_ROOT: Path | None = None


def set_trusted_paths(paths: list[Path]) -> None:
    """Add trusted directories that file tools can access beyond the workspace.

    Used to allow the agent to write to its own data directory (e.g. ~/.bytia-kode/)
    regardless of the current working directory.
    """
    _TRUSTED_PATHS.extend(p.resolve() for p in paths)


def set_workspace_root(root: Path) -> None:
    """Set the project workspace root for path validation.

    Called once at startup with the resolved project directory.
    Falls back to Path.cwd() if never called.
    """
    global _WORKSPACE_ROOT
    _WORKSPACE_ROOT = root.resolve()

_DEFAULT_BINARIES = {
    "ls", "pwd", "echo", "git", "grep", "find", "mkdir", "rmdir", "touch",
    "mv", "cp", "rm", "wc", "date", "chmod", "df", "du", "head", "tail",
    "curl", "wget", "scp", "ssh",
    "uv", "python", "python3", "pip", "pip3",
    "rg", "bat", "eza", "tokei", "shellcheck",
    "wsl",
}

_DANGEROUS_PATTERNS = [
    (r"<<", "heredoc"),
    (r"(?<!<)>(?!>)", "output redirection"),
]


def _load_allowed_binaries() -> set[str]:
    try:
        from bytia_kode.config import load_config
        config = load_config()
        return _DEFAULT_BINARIES | config.extra_binaries
    except Exception:
        logger.warning("Failed to load EXTRA_BINARIES from config, using defaults only")
        return _DEFAULT_BINARIES


_ALLOWED_BINARIES = _load_allowed_binaries()


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
    workspace = _WORKSPACE_ROOT or Path.cwd().resolve()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = workspace / candidate
    resolved = candidate.resolve()
    if workspace == resolved or workspace in resolved.parents:
        return resolved
    for trusted in _TRUSTED_PATHS:
        if trusted in resolved.parents:
            return resolved
    raise PermissionError(f"Security violation: path escapes workspace: {path}")


def _read_file_lines(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as fh:
        return fh.readlines()


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _create_backup(path: Path) -> Path:
    """Create a timestamped backup of a file before editing.

    Uses shutil.copy2 for atomic copy preserving metadata.
    Backup location: <file>.backup-YYYYMMDD-HHMMSS
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.parent / f"{path.name}.backup-{timestamp}"
    shutil.copy2(path, backup)
    return backup


class BashTool(Tool):
    name = "bash"
    description = (
        "Execute a SINGLE shell command (no pipes, chains, redirects, or heredocs). "
        "For file operations use file_write or file_edit instead. "
        "Call bash multiple times for sequential commands."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to execute"},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 60},
            "workdir": {"type": "string", "description": "Working directory", "default": "."},
        },
        "required": ["command"],
    }

    @staticmethod
    def _validate_command_safety(command: str) -> ToolResult | None:
        """Reject shell constructs that shlex.split + create_subprocess_exec cannot handle.

        The bash tool uses create_subprocess_exec which does NOT invoke a shell.
        This means shell operators (pipes, redirects, heredocs, chains) are NOT
        interpreted — they are passed as literal arguments to the binary, causing
        catastrophic results (e.g., 'mkdir -p dir && cat << EOF' creates dozens
        of garbage directories from the heredoc content).

        Returns None if safe, or a ToolResult(error=True) with guidance.
        """
        dangerous = [
            (r"<<", "heredoc"),
            (r">>", "append redirection"),
            (r"(?<!<)>(?!>)", "output redirection"),
            (r"\|", "pipe"),
            (r"&&", "command chain"),
            (r"\|\|", "or-chain"),
            (r";", "command separator"),
            (r"\$\(", "command substitution"),
            (r"`[^`]*`", "backtick substitution"),
        ]
        for pattern, name in dangerous:
            if re.search(pattern, command):
                return ToolResult(
                    output=(
                        f"Security policy: {name} not allowed in bash tool. "
                        f"This tool uses subprocess.exec (no shell), so operators like "
                        f"|, &&, >, << are NOT interpreted — they become literal arguments. "
                        f"Use file_write or file_edit to create/modify files. "
                        f"Call bash multiple times for sequential commands."
                    ),
                    error=True,
                )
        return None

    async def execute(self, command: str, timeout: int = 60, workdir: str = ".", on_subprocess=None, **_) -> ToolResult:
        try:
            safety_check = self._validate_command_safety(command)
            if safety_check is not None:
                return safety_check

            argv = shlex.split(command)
            if not argv:
                return ToolResult(output="Security policy: empty command is not allowed", error=True)

            command_base = Path(argv[0]).name
            if command_base not in _ALLOWED_BINARIES:
                hint = ""
                if command_base == "cd":
                    hint = " Hint: use the 'workdir' parameter to set the working directory."
                return ToolResult(
                    output=f"Security policy violation: command '{command_base}' is not allowed.{hint} Allowed: {', '.join(sorted(_ALLOWED_BINARIES))}.",
                    error=True,
                )

            process = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(_resolve_workspace_path(workdir)),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            if on_subprocess:
                on_subprocess(process)
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            output = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")
            if stderr_text:
                output += f"\nSTDERR:\n{stderr_text}"
            if on_subprocess:
                on_subprocess(None)
            return ToolResult(output=output[:50000], error=process.returncode != 0)
        except asyncio.TimeoutError:
            if on_subprocess:
                on_subprocess(None)
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


class FileEditTool(Tool):
    """Search/replace edits in files — the backbone of agentic coding.

    Two strategies:
      - 'replace': find exact old_text and replace with new_text (default, safe)
      - 'create': create a new file with the given content (fails if file exists unless force=True)

    Security: all paths resolved against workspace, no escapes.
    """

    name = "file_edit"
    description = (
        "Edit a file by replacing exact text matches. "
        "Use 'replace' strategy to find/replace specific text, or 'create' to make a new file. "
        "For replace: old_text must match exactly (including whitespace/indentation). "
        "Returns a unified diff showing what changed."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to edit",
            },
            "strategy": {
                "type": "string",
                "enum": ["replace", "create"],
                "description": "'replace' to find/replace text in existing file, 'create' to make a new file",
                "default": "replace",
            },
            "old_text": {
                "type": "string",
                "description": "(replace only) Exact text to find — must match including whitespace",
            },
            "new_text": {
                "type": "string",
                "description": "(replace only) Text to replace old_text with",
            },
            "content": {
                "type": "string",
                "description": "(create only) Full content for the new file",
            },
            "replace_all": {
                "type": "boolean",
                "description": "Replace all occurrences (default: only the first)",
                "default": "false",
            },
            "force": {
                "type": "boolean",
                "description": "(create only) Overwrite if file already exists",
                "default": "false",
            },
        },
        "required": ["path"],
    }

    async def execute(
        self,
        path: str,
        strategy: str = "replace",
        old_text: str | None = None,
        new_text: str | None = None,
        content: str | None = None,
        replace_all: bool = False,
        force: bool = False,
        **_,
    ) -> ToolResult:
        try:
            resolved = _resolve_workspace_path(path)
        except PermissionError as exc:
            return ToolResult(output=str(exc), error=True)

        if strategy == "create":
            return await self._create_file(resolved, content, force)
        elif strategy == "replace":
            return await self._replace_text(resolved, old_text, new_text, replace_all)
        else:
            return ToolResult(
                output=f"Unknown strategy: {strategy!r}. Use 'replace' or 'create'.",
                error=True,
            )

    async def _create_file(
        self, path: Path, content: str | None, force: bool
    ) -> ToolResult:
        if content is None:
            return ToolResult(
                output="Strategy 'create' requires 'content' parameter.", error=True
            )
        if path.exists() and not force:
            return ToolResult(
                output=f"File already exists: {path}. Use force=True to overwrite.",
                error=True,
            )
        try:
            await asyncio.to_thread(_write_file, path, content)
            lines = content.count("\n") + (0 if content.endswith("\n") else 1)
            return ToolResult(
                output=f"Created {path} ({lines} lines, {len(content)} chars)"
            )
        except Exception as exc:
            logger.error("file_edit create error: %s", exc)
            return ToolResult(output=f"Failed to create file: {exc}", error=True)

    async def _replace_text(
        self,
        path: Path,
        old_text: str | None,
        new_text: str | None,
        replace_all: bool,
    ) -> ToolResult:
        if old_text is None:
            return ToolResult(
                output="Strategy 'replace' requires 'old_text' parameter.", error=True
            )
        if new_text is None:
            new_text = ""
        if not path.exists():
            return ToolResult(output=f"File not found: {path}", error=True)
        if path.is_dir():
            return ToolResult(output=f"Path is a directory, not a file: {path}", error=True)

        try:
            original = await asyncio.to_thread(path.read_text, "utf-8")
        except Exception as exc:
            return ToolResult(output=f"Failed to read file: {exc}", error=True)

        if old_text not in original:
            # Provide helpful context: show nearby lines if partial match
            return self._no_match_help(original, old_text, path)

        count = original.count(old_text)
        if count > 1 and not replace_all:
            return ToolResult(
                output=(
                    f"Found {count} occurrences of old_text in {path}. "
                    f"Use replace_all=True to replace all, or provide more context "
                    f"to match a single occurrence."
                ),
                error=True,
            )

        modified = original.replace(old_text, new_text) if replace_all else original.replace(old_text, new_text, 1)

        # Create backup before writing
        backup_path = await asyncio.to_thread(_create_backup, path)

        try:
            await asyncio.to_thread(_write_file, path, modified)
        except Exception as exc:
            # Rollback: restore original
            try:
                await asyncio.to_thread(_write_file, path, original)
            except Exception:
                pass  # Best effort rollback
            return ToolResult(output=f"Failed to write file (rolled back): {exc}", error=True)

        diff = _make_unified_diff(original, modified, str(path))
        return ToolResult(
            output=(
                f"Replaced {count if replace_all else 1} occurrence(s) in {path}\n"
                f"Backup: {backup_path}\n"
                f"{diff}"
            )
        )

    def _no_match_help(self, original: str, old_text: str, path: Path) -> ToolResult:
        """Provide helpful diagnostics when old_text is not found."""
        # Check for whitespace issues
        stripped_old = old_text.strip()
        if stripped_old in original:
            return ToolResult(
                output=(
                    f"old_text not found in {path}, but a match exists with different "
                    f"leading/trailing whitespace. Check indentation and line endings."
                ),
                error=True,
            )

        # Check for partial match (first line)
        first_line = old_text.split("\n")[0].strip()
        if first_line:
            for i, line in enumerate(original.split("\n"), 1):
                if first_line in line:
                    return ToolResult(
                        output=(
                            f"old_text not found in {path}. "
                            f"Partial match on line {i}: '{line.strip()[:80]}'. "
                            f"Check for differences in surrounding lines."
                        ),
                        error=True,
                    )

        return ToolResult(
            output=f"old_text not found in {path}. No partial matches detected.",
            error=True
        )


def _make_unified_diff(old: str, new: str, path: str, context: int = 3) -> str:
    """Generate a compact unified diff for display."""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}", n=context)
    result = "".join(diff)
    if not result:
        return "(no changes)"
    # Truncate very long diffs
    if len(result) > 10000:
        result = result[:10000] + f"\n... (diff truncated at 10000 chars)"
    return result


class ReadContextTool(Tool):
    """Read workspace context file (project structure, language, git info)."""

    name = "read_context"
    description = (
        "Read the workspace context file containing project structure, "
        "language, framework, git info, and B-KODE.md status. "
        "Use when you need to understand the current project before working on it."
    )
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> ToolResult:
        from bytia_kode.context import ensure_context

        try:
            path = ensure_context(Path.cwd())
            content = path.read_text(encoding="utf-8")
            return ToolResult(output=content)
        except Exception as exc:
            logger.error("read_context error: %s", exc)
            return ToolResult(output=f"Failed to read context: {exc}", error=True)


            return ToolResult(output=f"Failed to read context: {exc}", error=True)


class GrepTool(Tool):
    name = "grep"
    description = "Search file contents for a pattern. Returns matching lines with file paths and line numbers."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern to search for"},
            "path": {"type": "string", "description": "File or directory to search in (default: workspace)"},
            "include": {"type": "string", "description": "Glob pattern for file names (e.g. '*.py', '*.{ts,tsx}')"},
        },
        "required": ["pattern"],
    }

    async def execute(self, pattern: str, path: str = ".", include: str = "", **_) -> ToolResult:
        try:
            import re as _re
            resolved = _resolve_workspace_path(path)
            if not resolved.is_dir():
                lines = await asyncio.to_thread(self._search_file, resolved, pattern)
                output = "\n".join(lines) if lines else "No matches found."
                return ToolResult(output=output)
            glob_pattern = include or "*"
            results = []
            for file_path in sorted(resolved.rglob(glob_pattern)):
                if file_path.is_file() and not any(p.startswith(".") for p in file_path.relative_to(resolved).parts):
                    if file_path.stat().st_size > 1_000_000:
                        continue
                    lines = await asyncio.to_thread(self._search_file, file_path, pattern)
                    results.extend(lines)
                if len(results) > 200:
                    results.append("... (truncated at 200 matches)")
                    break
            output = "\n".join(results) if results else "No matches found."
            return ToolResult(output=output)
        except PermissionError as exc:
            return ToolResult(output=str(exc), error=True)
        except Exception as exc:
            return ToolResult(output=str(exc), error=True)

    @staticmethod
    def _search_file(file_path: Path, pattern: str) -> list[str]:
        import re as _re
        results = []
        try:
            regex = _re.compile(pattern, _re.IGNORECASE)
            text = file_path.read_text(errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    results.append(f"{file_path}:{i}: {line.strip()[:200]}")
        except Exception:
            pass
        return results


class GlobTool(Tool):
    name = "glob"
    description = "Find files matching a pattern. Returns file paths relative to workspace."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py', 'src/**/*.ts')"},
            "path": {"type": "string", "description": "Directory to search in (default: workspace)"},
        },
        "required": ["pattern"],
    }

    async def execute(self, pattern: str, path: str = ".", **_) -> ToolResult:
        try:
            resolved = _resolve_workspace_path(path)
            if not resolved.is_dir():
                return ToolResult(output=f"Not a directory: {path}", error=True)
            matches = []
            for p in sorted(resolved.glob(pattern)):
                rel = p.relative_to(resolved)
                matches.append(f"{rel}" + ("/" if p.is_dir() else ""))
                if len(matches) >= 500:
                    matches.append("... (truncated at 500 results)")
                    break
            output = "\n".join(matches) if matches else "No files found matching pattern."
            return ToolResult(output=output)
        except PermissionError as exc:
            return ToolResult(output=str(exc), error=True)
        except Exception as exc:
            return ToolResult(output=str(exc), error=True)


class TreeTool(Tool):
    name = "tree"
    description = "Show directory structure as a tree. Returns file and folder hierarchy."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory to show (default: workspace)"},
            "depth": {"type": "integer", "description": "Max depth (default: 3)"},
        },
    }

    async def execute(self, path: str = ".", depth: int = 3, **_) -> ToolResult:
        try:
            resolved = _resolve_workspace_path(path)
            if not resolved.is_dir():
                return ToolResult(output=f"Not a directory: {path}", error=True)
            lines = await asyncio.to_thread(self._build_tree, resolved, resolved, depth, 0)
            output = "\n".join(lines) if lines else "Empty directory."
            return ToolResult(output=output)
        except PermissionError as exc:
            return ToolResult(output=str(exc), error=True)
        except Exception as exc:
            return ToolResult(output=str(exc), error=True)

    @staticmethod
    def _build_tree(base: Path, current: Path, max_depth: int, current_depth: int) -> list[str]:
        if current_depth > max_depth:
            return []
        results = []
        try:
            entries = sorted(current.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return []
        for i, entry in enumerate(entries):
            name = entry.name
            if name.startswith(".") or name == "__pycache__":
                continue
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            prefix = "    " * current_depth
            if entry.is_dir():
                results.append(f"{prefix}{connector}{name}/")
                results.extend(TreeTool._build_tree(base, entry, max_depth, current_depth + 1))
            else:
                size = entry.stat().st_size
                if size > 1024 * 1024:
                    size_str = f" ({size // (1024*1024)}MB)"
                elif size > 1024:
                    size_str = f" ({size // 1024}KB)"
                else:
                    size_str = ""
                results.append(f"{prefix}{connector}{name}{size_str}")
            if len(results) > 300:
                results.append("... (truncated)")
                break
        return results


class ToolRegistry:
    """Registry of available tools."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._register_defaults()

    def _register_defaults(self):
        for tool_cls in [BashTool, FileReadTool, FileWriteTool, FileEditTool, WebFetchTool, ReadContextTool, GrepTool, GlobTool, TreeTool]:
            self.register(tool_cls())

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def get_tool_defs(self) -> list[ToolDef]:
        return [t.to_tool_def() for t in self._tools.values()]

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    async def execute(self, tool_name: str, arguments: dict[str, Any] | None = None, *, on_subprocess=None) -> ToolResult:
        if arguments is None:
            arguments = {}
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(output=f"Unknown tool: {tool_name}", error=True)
        if on_subprocess is not None:
            arguments = {**arguments, "on_subprocess": on_subprocess}
        return await tool.execute(**arguments)
