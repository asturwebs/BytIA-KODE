# B-KODE.md — BytIA KODE Project Instructions

## Project

BytIA KODE is an agentic TUI for assisted development with terminal and Telegram bot. Built with Python 3.11+ and Textual.

**Contexto de ejecución:** Consulta `CONTEXT.md` para estado real del proyecto, configuración, skills y patrones de código.

## Architecture

- `agent.py` — Agentic loop (think → act → observe)
- `tui.py` — Textual TUI interface
- `providers/` — OpenAI-compatible provider clients (router, fallback, local)
- `tools/` — Registered tools (bash, file_read, file_write, file_edit, web_fetch)
- `skills/` — Skill loader and persistence
- `prompts/` — Constitutional identity (YAML)

## Development

- **Package manager:** `uv` (never pip)
- **Install:** `uv sync`
- **Run:** `uv run bytia-kode`
- **Reinstall as tool:** `uv tool install --force --reinstall .`
- **Test:** `uv run pytest`
- **Lint/validate:** `uv run pytest` (pre-commit hook runs metadata + secret scan)

## Code Style

- Python 3.11+, type hints recommended
- No comments unless requested
- Ruff for linting
- Follow existing patterns

## Key Patterns

- All paths resolved via `_resolve_workspace_path()` (sandbox to CWD)
- Tools return `ToolResult(output, error)` — never raise
- Provider clients use OpenAI-compatible `/v1/chat/completions`
- Context management: summarize at 75% threshold, fallback to truncation
- File edits use `file_edit` tool (never raw `file_write` for modifications)

## Security

- Bash: allowlist of safe binaries only
- Files: path traversal blocked, workspace sandbox
- No secrets in code (pre-commit hook scans)

## Logging

- `~/.bytia-kode/logs/bytia-kode.log` — rotating file (1MB, 3 backups)
- Level via `LOG_LEVEL` in `.env` (default: `INFO`)
- Custom path via `LOG_FILE` in `.env`
- All modules: `agent`, `tui`, `providers/`, `tools/`, `session`, `skills/`, `telegram/`

## Version

Current release: 0.5.2-dev
