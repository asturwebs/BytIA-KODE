# Multi-Workspace CONTEXT.md

**Date:** 2026-04-07
**Status:** Approved
**Scope:** B-KODE v0.5.2

## Problem

B-KODE is workspace-aware (tools operate on `Path.cwd()`, searches `B-KODE.md` in cwd and parents), but has no per-workspace operational context. CONTEXT.md exists only in the B-KODE repo, is tracked in git with local user data, and the agent never reads it.

When B-KODE runs in a different project, it has no knowledge of that project's structure, language, tooling, or state.

## Solution

Auto-generate a CONTEXT.md per workspace on first run. Store in `~/.bytia-kode/contexts/` using a deterministic hash of the workspace path. Expose as a tool (`read_context`) that the agent invokes on demand.

## Storage

```
~/.bytia-kode/contexts/
├── a3f2b1c8.md    # /home/user/proyectos/bytia-kode
├── 7d4e9f0a.md    # /home/user/proyectos/otro-proyecto
└── ...
```

**Hash:** `hashlib.sha256(cwd.encode()).hexdigest()[:8]`

Same path always maps to the same file. No collisions. No human-readable names needed — the content identifies the project.

## Generation

**Trigger:** Only when the context file for the current workspace does not exist.

**Location in code:** New module `src/bytia_kode/context.py`.

**When:** Checked at startup in `run_tui()` (TUI) and `main()` (Telegram bot).

**Detection logic** (graceful degradation — each section is optional):

```markdown
# Workspace Context

## Project
- **Name:** (git remote name, or dirname)
- **Path:** /absolute/path/to/workspace
- **Language:** Python 3.13 (from file extensions or pyproject.toml/package.json)
- **Framework:** textual, fastapi, etc. (from dependencies)
- **Build:** uv, npm, etc. (from config files)
- **Test:** pytest, jest, etc. (from config files)
- **Lint:** ruff, eslint, etc. (from config files)

## Structure
```
src/           # source
tests/         # tests
docs/          # documentation
```

## Git
- **Branch:** main
- **Recent commits:**
  - abc1234 feat: description (2h ago)
  - def5678 fix: description (1d ago)

## B-KODE.md
- **Found:** yes/no
- **Path:** /absolute/path/B-KODE.md
```

**Detection order:**
1. Check for `pyproject.toml` → Python project
2. Check for `package.json` → Node.js project
3. Check for `Cargo.toml` → Rust project
4. Check for `go.mod` → Go project
5. Fallback: scan file extensions for language detection
6. Git info: `git rev-parse --abbrev-ref HEAD`, `git log --oneline -3`
7. Directory tree: top-level dirs/files (max depth 1, skip hidden/common dirs)

## Tool: `read_context`

New tool in `tools/registry.py`:

```python
name = "read_context"
description = "Read the workspace context file (project structure, language, tooling, git info). Use when you need to understand the current project before working on it."
```

**Behavior:**
1. Compute hash of `Path.cwd()`
2. Check if `~/.bytia-kode/contexts/<hash>.md` exists
3. If not exists → generate it first, then read
4. Return contents as `ToolResult`

This means the tool auto-generates if needed — no separate generation step required.

## Command: `/context`

TUI and Telegram command to force-regenerate the workspace context.

- Deletes existing context file for current workspace
- Re-generates from scratch
- Returns summary of what was detected

## B-KODE.md Nudge

Add to B-KODE.md:

```markdown
## Context
Para estado operativo del workspace actual, usa la tool `read_context`.
```

This goes in the system prompt (B-KODE.md is always loaded), so the agent knows the tool exists without auto-injecting the full context.

## Git Cleanup

1. `git rm --cached CONTEXT.md` — remove from tracking (file stays local)
2. Add `CONTEXT.md` to `.gitignore`
3. No `CONTEXT.md.example` needed — the agent generates it

## Files Changed

| File | Action |
|------|--------|
| `src/bytia_kode/context.py` | **New** — workspace detection and CONTEXT.md generation |
| `src/bytia_kode/tools/registry.py` | **Modify** — add `read_context` tool |
| `src/bytia_kode/tui.py` | **Modify** — add `/context` command, startup check |
| `src/bytia_kode/telegram/bot.py` | **Modify** — add `/context` command |
| `B-KODE.md` | **Modify** — add Context nudge section |
| `.gitignore` | **Modify** — add `CONTEXT.md` |
| `CONTEXT.md` | **Remove from git tracking** (keep local) |

## Not In Scope

- Auto-update on file changes (user runs `/context` to refresh)
- Context injection in system prompt (tool-based, not auto)
- Context for Claude Code / other agents (B-KODE only)
