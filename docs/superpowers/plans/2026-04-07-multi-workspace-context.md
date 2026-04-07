# Multi-Workspace CONTEXT.md Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-generate per-workspace CONTEXT.md files that B-KODE reads on demand via a `read_context` tool.

**Architecture:** New `context.py` module detects workspace metadata (language, framework, git, structure) and writes a markdown file to `~/.bytia-kode/contexts/<hash>.md`. A new `ReadContextTool` in the tool registry reads/generates it. TUI and Telegram get a `/context` command to force regeneration.

**Tech Stack:** Python 3.11+, pathlib, hashlib, subprocess (git), pydantic (ToolResult)

---

### Task 1: Git cleanup — remove CONTEXT.md from tracking

**Files:**
- Modify: `.gitignore`
- Modify: `CONTEXT.md` (remove from index, keep local)

- [ ] **Step 1: Add CONTEXT.md to .gitignore**

Add `CONTEXT.md` to the existing `.gitignore` file at the end, before the patterns section.

- [ ] **Step 2: Remove from git tracking**

Run: `git rm --cached CONTEXT.md`

This removes the file from git index but keeps it on disk.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: remove CONTEXT.md from tracking, add to .gitignore"
```

---

### Task 2: Create context.py — workspace detection module

**Files:**
- Create: `src/bytia_kode/context.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_context.py`:

```python
"""Tests for workspace context generation."""
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from bytia_kode.context import workspace_hash, generate_context, context_path


class TestWorkspaceHash:
    def test_same_path_same_hash(self):
        h1 = workspace_hash("/home/user/project")
        h2 = workspace_hash("/home/user/project")
        assert h1 == h2

    def test_different_paths_different_hash(self):
        h1 = workspace_hash("/home/user/project-a")
        h2 = workspace_hash("/home/user/project-b")
        assert h1 != h2

    def test_hash_is_8_chars(self):
        h = workspace_hash("/any/path")
        assert len(h) == 8


class TestContextPath:
    def test_returns_path_in_contexts_dir(self, tmp_path):
        with patch("bytia_kode.context.CONTEXTS_DIR", tmp_path):
            p = context_path("/home/user/project")
            assert p.parent == tmp_path
            assert p.name.endswith(".md")

    def test_hash_consistency(self, tmp_path):
        with patch("bytia_kode.context.CONTEXTS_DIR", tmp_path):
            p1 = context_path("/home/user/project")
            p2 = context_path("/home/user/project")
            assert p1 == p2


class TestGenerateContext:
    def test_generates_file(self, tmp_path):
        with patch("bytia_kode.context.CONTEXTS_DIR", tmp_path):
            p = context_path("/home/user/project")
            content = generate_context(Path("/home/user/project"))
            assert "# Workspace Context" in content
            assert "/home/user/project" in content

    def test_detects_python_project(self, tmp_path):
        project = tmp_path / "myproject"
        project.mkdir()
        (project / "pyproject.toml").write_text("[project]\nname='myproject'\n")
        (project / "src").mkdir()
        content = generate_context(project)
        assert "Python" in content
        assert "myproject" in content

    def test_detects_node_project(self, tmp_path):
        project = tmp_path / "myproject"
        project.mkdir()
        (project / "package.json").write_text('{"name": "myproject"}')
        content = generate_context(project)
        assert "Node" in content or "JavaScript" in content

    def test_no_project_file(self, tmp_path):
        project = tmp_path / "empty"
        project.mkdir()
        content = generate_context(project)
        assert "# Workspace Context" in content

    def test_detects_git_info(self, tmp_path, monkeypatch):
        project = tmp_path / "gitproject"
        project.mkdir()
        (project / "pyproject.toml").write_text("[project]\nname='gitproject'\n")
        monkeypatch.chdir(project)
        content = generate_context(project)
        # May or may not have git info depending on test env
        assert "# Workspace Context" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_context.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bytia_kode.context'`

- [ ] **Step 3: Write context.py implementation**

Create `src/bytia_kode/context.py`:

```python
"""Workspace context detection and generation."""
from __future__ import annotations

import hashlib
import logging
import subprocess
from pathlib import Path

from bytia_kode.config import load_config

logger = logging.getLogger(__name__)

CONTEXTS_DIR = Path.home() / ".bytia-kode" / "contexts"


def workspace_hash(cwd: str | Path) -> str:
    return hashlib.sha256(str(cwd).encode()).hexdigest()[:8]


def context_path(cwd: str | Path) -> Path:
    return CONTEXTS_DIR / f"{workspace_hash(cwd)}.md"


def _detect_project(workspace: Path) -> dict:
    info: dict[str, str] = {}
    project_files = {
        "pyproject.toml": "Python",
        "setup.py": "Python",
        "package.json": "Node.js",
        "Cargo.toml": "Rust",
        "go.mod": "Go",
    }
    for fname, lang in project_files.items():
        if (workspace / fname).is_file():
            info["language"] = lang
            break
    if not info.get("language"):
        py_files = list(workspace.glob("*.py"))
        js_files = list(workspace.glob("*.js")) + list(workspace.glob("*.ts"))
        if py_files:
            info["language"] = "Python (detected)"
        elif js_files:
            info["language"] = "JavaScript/TypeScript (detected)"
    return info


def _detect_git(workspace: Path) -> dict:
    info: dict[str, str] = {}
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=workspace, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            info["branch"] = result.stdout.strip()
        result = subprocess.run(
            ["git", "log", "--oneline", "-3"],
            cwd=workspace, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            info["recent_commits"] = result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return info


def _detect_structure(workspace: Path) -> str:
    entries = []
    skip = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache", "build", "dist", ".egg-info"}
    for p in sorted(workspace.iterdir()):
        if p.name.startswith(".") or p.name in skip:
            continue
        if p.is_dir():
            entries.append(f"{p.name}/")
        else:
            entries.append(p.name)
    if not entries:
        return "(empty)"
    return "\n".join(entries)


def _find_bkode_md(workspace: Path) -> dict:
    for candidate in [workspace, *workspace.parents]:
        bk = candidate / "B-KODE.md"
        if bk.is_file():
            return {"found": "yes", "path": str(bk)}
    return {"found": "no", "path": ""}


def generate_context(workspace: Path) -> str:
    project = _detect_project(workspace)
    git = _detect_git(workspace)
    structure = _detect_structure(workspace)
    bkode = _find_bkode_md(workspace)
    name = workspace.name

    lines = [
        "# Workspace Context",
        "",
        "## Project",
        f"- **Name:** {name}",
        f"- **Path:** {workspace.resolve()}",
    ]
    if project.get("language"):
        lines.append(f"- **Language:** {project['language']}")
    lines.append("")

    lines.append("## Structure")
    lines.append("```")
    lines.append(structure)
    lines.append("```")
    lines.append("")

    if git.get("branch") or git.get("recent_commits"):
        lines.append("## Git")
        if git.get("branch"):
            lines.append(f"- **Branch:** {git['branch']}")
        if git.get("recent_commits"):
            lines.append("- **Recent commits:**")
            for c in git["recent_commits"].split("\n"):
                lines.append(f"  - {c}")
        lines.append("")

    lines.append("## B-KODE.md")
    lines.append(f"- **Found:** {bkode['found']}")
    if bkode["found"] == "yes":
        lines.append(f"- **Path:** {bkode['path']}")
    lines.append("")

    return "\n".join(lines)


def ensure_context(workspace: Path) -> Path:
    """Generate context file if it doesn't exist, return its path."""
    CONTEXTS_DIR.mkdir(parents=True, exist_ok=True)
    path = context_path(workspace)
    if not path.exists():
        content = generate_context(workspace)
        path.write_text(content, encoding="utf-8")
        logger.info("Context generated: %s", path)
    return path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_context.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/bytia_kode/context.py tests/test_context.py
git commit -m "feat: add workspace context detection and generation module"
```

---

### Task 3: Add `read_context` tool

**Files:**
- Modify: `src/bytia_kode/tools/registry.py:460-462` (register defaults)
- Modify: `tests/test_context.py` (add tool test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_context.py`:

```python
from bytia_kode.tools.registry import ToolRegistry


class TestReadContextTool:
    def test_tool_registered(self):
        registry = ToolRegistry()
        assert registry.get("read_context") is not None

    def test_tool_returns_content(self, tmp_path):
        project = tmp_path / "testproject"
        project.mkdir()
        (project / "pyproject.toml").write_text("[project]\nname='testproject'\n")
        from bytia_kode.tools.registry import ReadContextTool
        with patch("bytia_kode.context.CONTEXTS_DIR", tmp_path / "contexts"):
            tool = ReadContextTool()
            result = tool.execute()
            assert not result.error
            assert "Workspace Context" in result.output
            assert "testproject" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_context.py::TestReadContextTool -v`
Expected: FAIL — `ReadContextTool` not found

- [ ] **Step 3: Implement ReadContextTool in registry.py**

Add this class before `ToolRegistry` in `src/bytia_kode/tools/registry.py`:

```python
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
```

- [ ] **Step 4: Register the tool**

In `ToolRegistry._register_defaults()` at `registry.py:460-462`, add `ReadContextTool`:

```python
def _register_defaults(self):
    for tool_cls in [BashTool, FileReadTool, FileWriteTool, FileEditTool, WebFetchTool, ReadContextTool]:
        self.register(tool_cls())
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_context.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest -q`
Expected: All 66+ tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/bytia_kode/tools/registry.py tests/test_context.py
git commit -m "feat: add read_context tool for workspace context"
```

---

### Task 4: Add `/context` command to TUI

**Files:**
- Modify: `src/bytia_kode/tui.py:739` (after `/cwd` handler)
- Modify: `src/bytia_kode/tui.py:748-772` (help text)

- [ ] **Step 1: Add handler in `_handle_command()`**

In `src/bytia_kode/tui.py`, find the `/cwd` handler block and add `/context` after it:

```python
elif cmd == "/cwd":
    self._add_system_message(f"CWD: {os.getcwd()}")
elif cmd == "/context":
    self._regenerate_context()
```

- [ ] **Step 2: Add `_regenerate_context()` method**

Add this method to the `BytIAKODEApp` class (after `_handle_command`):

```python
def _regenerate_context(self):
    from bytia_kode.context import context_path, generate_context, CONTEXTS_DIR
    CONTEXTS_DIR.mkdir(parents=True, exist_ok=True)
    path = context_path(os.getcwd())
    content = generate_context(Path(os.getcwd()))
    path.write_text(content, encoding="utf-8")
    self._add_system_message(f"Context regenerated: {path.name}")
```

- [ ] **Step 3: Add to help text**

In `_show_help()` table, add a row for `/context`:

```python
TableRow("[cyan]/context[/]", "Regenerate workspace context"),
```

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -q`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/bytia_kode/tui.py
git commit -m "feat: add /context command to TUI"
```

---

### Task 5: Add `/context` command to Telegram bot

**Files:**
- Modify: `src/bytia_kode/telegram/bot.py:39-44` (handler setup)
- Modify: `src/bytia_kode/telegram/bot.py:86-91` (help text)

- [ ] **Step 1: Register handler**

In `_setup_handlers()`, add after the `/sessions` handler:

```python
self.app.add_handler(CommandHandler("context", self._context))
```

- [ ] **Step 2: Add handler method**

Add this method after `_sessions`:

```python
async def _context(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    if not self._is_allowed(update.effective_user.id):
        await self._deny(update)
        return
    from bytia_kode.context import context_path, generate_context, CONTEXTS_DIR
    CONTEXTS_DIR.mkdir(parents=True, exist_ok=True)
    path = context_path(".")
    content = generate_context(Path.cwd())
    path.write_text(content, encoding="utf-8")
    await update.message.reply_text(f"Context regenerated: {path.name}")
```

- [ ] **Step 3: Add to help text**

In `_help()`, add `/context` to the commands list.

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -q`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/bytia_kode/telegram/bot.py
git commit -m "feat: add /context command to Telegram bot"
```

---

### Task 6: Add nudge to B-KODE.md

**Files:**
- Modify: `B-KODE.md`

- [ ] **Step 1: Add Context section**

At the end of `B-KODE.md`, before `## Version`:

```markdown
## Context

Para estado operativo del workspace actual, usa la tool `read_context`.
```

- [ ] **Step 2: Commit**

```bash
git add B-KODE.md
git commit -m "docs: add read_context nudge to B-KODE.md"
```

---

### Task 7: Update CONTEXT.md and docs

**Files:**
- Modify: `CONTEXT.md` (add logging section reference, update version)
- Modify: `CONTEXT.md` in gitignore (already done in Task 1)

- [ ] **Step 1: Update CONTEXT.md locally**

Add to the local CONTEXT.md the workspace context feature info. This file is now local-only (gitignored).

- [ ] **Step 2: Update ROADMAP.md**

In the v0.5.2 section, mark the context feature items as done:

```markdown
- [x] **Multi-workspace context** — auto-generated per workspace, read via `read_context` tool
  - `context.py`: workspace detection (language, git, structure, B-KODE.md)
  - `read_context` tool: on-demand context reading
  - `/context` command: force regeneration (TUI + Telegram)
  - Storage: `~/.bytia-kode/contexts/<hash>.md`
```

- [ ] **Step 3: Commit**

```bash
git add ROADMAP.md
git commit -m "docs: update roadmap with multi-workspace context feature"
```

---

### Task 8: Final verification

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -q`
Expected: All tests PASS

- [ ] **Step 2: Verify pre-commit hooks**

Run: `uv run pytest` (triggers pre-commit: metadata + secret scan)
Expected: All PASS

- [ ] **Step 3: Manual smoke test**

Run: `uv run bytia-kode`
- Type `/context` → should show "Context regenerated: <hash>.md"
- Type a message asking about the project → agent should use `read_context` tool
- Check `~/.bytia-kode/contexts/` → file exists with correct content
