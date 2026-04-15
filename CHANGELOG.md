# Changelog

## [0.7.1] - 2026-04-15

### Fixed

- **Reasoning tag leak**: `<reasoning>` tags no longer stored in message history. Prevents tag pollution in subsequent model turns. Reasoning is still displayed in TUI ThinkingBlock but not persisted.
- **Fallback notification missing**: `provider_used` chunk now emitted in exception handler path, not just initial provider selection. User sees "Switched to: Fallback" on within-request provider changes.
- **Circuit breaker recovery**: `get_healthy()` always walks full priority order. Primary circuit naturally retried after HALF_OPEN recovery (60s), regardless of previously active provider.
- **Security bypass**: Added `rmdir` to BashTool allowlist. Model no longer needs `file_write` + `python script.py` workaround for removing empty directories.
- **Duplicate system messages**: Removed `_add_system_message()` from reactive watcher `_on_provider_changed`. Notification now comes exclusively from chunk handler — no duplicates.
- **Stale venv**: Removed orphaned `uv tool install` (v0.5.3) from `~/.local/share/uv/tools/`. Single installation via project's editable `.venv`.

### Changed

- `(sin respuesta de texto)` replaces `[razonamiento sin respuesta de texto]` as empty response fallback.
- `get_healthy()` refactored: always evaluates from top of priority order, `preferred` parameter only used as last resort when all circuits are OPEN.

### Tests

- 110 passed — assertions updated for new reasoning storage behavior.

---

## v0.7.0 — 2026-04-15

### Added

- **Circuit Breaker**: CLOSED/OPEN/HALF_OPEN state machine for provider resilience. 3-failure threshold, 60s recovery timeout. `force_open()` for immediate circuit breaking on startup.
- **Auto-fallback**: Provider chain (primary → fallback → local) with automatic switching on failure. Loop-internal `continue` for seamless retry.
- **Provider signaling**: `("provider_used", name)` chunk type for agent→TUI provider communication.
- **Status line updates**: ActivityIndicator reflects active provider and model on switch.

---

## v0.6.1 — 2026-04-12

### Fixed

- Agentic loop infinite restart after tool execution.
- ToolRegistry.execute() accepts `on_subprocess` callback from Agent.

---

## v0.6.0 — 2026-04-11

### Added

- **Panic Buttons**: Escape (interrupt stream) + Ctrl+K (kill agent + subprocess).
- **Native exploration tools**: GrepTool, GlobTool, TreeTool.
- **Sandbox**: `_validate_command_safety()` blocks shell operators (pipes, redirects, heredocs, subshells).
- **Reasoning persistence**: Assistant messages store reasoning alongside text.
- **106 tests** passing.

---

## v0.5.0 — 2026-04-10

### Added

- 19 TUI themes with CSS.
- Streaming rendering with RichMarkdown.
- ThinkingBlock (collapsible reasoning).
- ToolBlock (color-coded execution output).
- Session management: /sessions, /load, /new, /reset.

---

## v0.4.0 — 2026-04-09

### Added

- Telegram bot with fail-secure authentication.
- Skills system (load, save, search, verify).
- Memory directories (contexto, decisiones, procedimientos, tecnologia).

---

## v0.3.0 — 2026-04-08

### Added

- BashTool, FileReadTool, FileWriteTool, FileEditTool, WebFetchTool.
- SQLite WAL session store.
- Session tools (list, load, search).

---

## v0.2.0 — 2026-04-07

### Added

- Multi-provider support (primary/fallback/local).
- httpx SSE streaming.
- OpenAI-compatible endpoint integration.

---

## v0.1.0 — 2026-04-06

### Added

- Basic Textual TUI.
- Agent with agentic loop.
- Tool call handling.
- B-KODE.md project instructions.
