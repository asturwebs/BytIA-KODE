"""Workspace context detection and generation."""
from __future__ import annotations

import hashlib
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

CONTEXTS_DIR = Path.home() / ".bytia-kode" / "contexts"


def workspace_hash(cwd: str | Path) -> str:
    """Deterministic 8-char hash of workspace path."""
    return hashlib.sha256(str(cwd).encode()).hexdigest()[:8]


def context_path(cwd: str | Path) -> Path:
    """Return the path where this workspace's context file should live."""
    return CONTEXTS_DIR / f"{workspace_hash(cwd)}.md"


def _detect_project(workspace: Path) -> dict:
    """Detect project language from config files."""
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
    """Detect git branch and recent commits."""
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
    """List top-level directory entries, skipping common noise."""
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
    """Search for B-KODE.md in workspace and parent dirs."""
    for candidate in [workspace, *workspace.parents]:
        bk = candidate / "B-KODE.md"
        if bk.is_file():
            return {"found": "yes", "path": str(bk)}
    return {"found": "no", "path": ""}


def generate_context(workspace: Path) -> str:
    """Generate a markdown CONTEXT.md content for the workspace."""
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
