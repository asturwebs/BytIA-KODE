# Changelog

## [0.7.4] - 2026-04-28

### Fixed

- **DeepSeek V4 error 400**: `reasoning_content` ahora se incluye en todos los mensajes `assistant` posteriores a un tool call cuando se usa DeepSeek en thinking mode. El flag `_has_had_tool_calls` (antes muerto) se activa correctamente y `_ensure_deepseek_reasoning()` parchea los mensajes antes de enviarlos a la API.
- **Streaming timeout (silent hang)**: `_stream_with_timeout()` envuelve el iterador SSE con `asyncio.wait_for()` por chunk (60s). Si el provider deja de emitir datos sin cerrar la conexión, se lanza `TimeoutError` en lugar de colgarse indefinidamente.
- **Cloud API polling storm**: `_poll_router_info()` ahora verifica `client.is_local` antes de llamar a `get_router_info()`. Solo el router local (localhost) recibe polling cada 5s. APIs cloud (DeepSeek, MiniMax, Z.ai) se saltan — su endpoint `/v1/models` no expone métricas de llama.cpp.

### Added

- `ProviderClient.is_local`: nueva propiedad que detecta si el provider es un servidor local (localhost/127.0.0.1).
- `Agent._stream_with_timeout()`: wrapper de iterador async con timeout por chunk.
- `Agent._ensure_deepseek_reasoning()`: parchea mensajes para cumplir requisitos de DeepSeek thinking mode.

## [0.7.3] - 2026-04-27

### Changed

- **SP cache**: system prompt cached per message count, avoids double rebuild per iteration (~500ms/iter saved).
- **Router polling**: paused during agent processing to eliminate unnecessary HTTP requests.
- **Placeholder**: reasoning text used as fallback instead of literal `(sin respuesta de texto)`, reducing history pollution.
- **Batch compression**: 5 messages at once (was 2), last 4 non-system messages always preserved, truncation for very old history.

### Tests

- 130 passed — no regressions

---


## [0.7.2] - 2026-04-26

### Added

- **DeepSeek V4 provider**: 5th provider slot with OpenAI-compatible endpoint (`api.deepseek.com`). Models: `deepseek-v4-flash` (default, fast MoE) and `deepseek-v4-pro` (thinking/reasoning). Configurable context limit via `DEEPSEEK_MAX_CONTEXT` env var (default 1M tokens). Priority 4 in chain: primary → fallback → minimax → deepseek → local.
- **Provider pinning (sticky)**: F3 manual provider selection now pins to the chosen provider. Agent uses pinned provider exclusively — no auto-fallback on failure. Unpin by switching back to Primary with F3. Auto-fallback (circuit breaker + priority walk) still works when no pin is set.
- **Context-aware provider switching**: Context limit updates on every F3 provider switch. DeepSeek gets configured limit (1M), others get agent default (262k), primary delegates to router polling.

### Fixed

- **`/model` table missing providers**: Hardcoded provider list in `_show_model_info()` now includes DeepSeek.
- **`_provider_display_name` missing**: Added "deepseek" → "DeepSeek" mapping.
- **Stale context on provider switch**: Switching from DeepSeek (1M ctx) to another provider no longer keeps the 1M limit. Each provider properly resets ctx.
- **Claude Code settings.json model override conflict**: `ANTHROPIC_DEFAULT_{SONNET,OPUS,HAIKU}_MODEL` GLM overrides in settings.json were overriding process env vars from provider aliases. Moved GLM model vars to `claude-zai` and `claude-zai-yolo` aliases explicitly. Each alias now controls its own models.
- **DeepSeek 400 Bad Request after tool calls**: `reasoning_content` from DeepSeek responses is now stored in `Message` and passed back in subsequent requests. Without this, DeepSeek rejects requests where the previous assistant turn included tool calls but `reasoning_content` was missing. Affects `ProviderResponse`, `Message`, `SessionStore` schema, and agent message persistence.

### Changed

- **Agent error handling**: Pinned provider failures now yield error and stop (user switches manually). Non-pinned failures still auto-fallback via circuit breaker (unchanged behavior).
- **`get_healthy()`**: Returns pinned provider unconditionally when set. Priority walk only used when no pin.
- **`.zshrc` aliases**: `claude-ds` added (DeepSeek Anthropic-compatible endpoint). `claude-zai` and `claude-zai-yolo` now carry explicit GLM model vars. `~/.bytia-banner` updated with new provider.

### Tests

- 130 passed — no regressions.

---

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

## [0.7.0] - 2026-04-15

### Added

- **Circuit Breaker**: CLOSED/OPEN/HALF_OPEN state machine for provider resilience. 3-failure threshold, 60s recovery timeout. `force_open()` for immediate circuit breaking on startup.
- **Auto-fallback**: Provider chain (primary → fallback → local) with automatic switching on failure. Loop-internal `continue` for seamless retry.
- **Provider signaling**: `("provider_used", name)` chunk type for agent→TUI provider communication.
- **Status line updates**: ActivityIndicator reflects active provider and model on switch.

---

## [0.6.1] - 2026-04-12

### Fixed

- Agentic loop infinite restart after tool execution.
- ToolRegistry.execute() accepts `on_subprocess` callback from Agent.

---

## [0.6.0] - 2026-04-11

### Added

- **Panic Buttons**: Escape (interrupt stream) + Ctrl+K (kill agent + subprocess).
- **Native exploration tools**: GrepTool, GlobTool, TreeTool.
- **Sandbox**: `_validate_command_safety()` blocks shell operators (pipes, redirects, heredocs, subshells).
- **Reasoning persistence**: Assistant messages store reasoning alongside text.
- **106 tests** passing.

---

## [0.5.0] - 2026-04-10

### Added

- 19 TUI themes with CSS.
- Streaming rendering with RichMarkdown.
- ThinkingBlock (collapsible reasoning).
- ToolBlock (color-coded execution output).
- Session management: /sessions, /load, /new, /reset.

---

## [0.4.0] - 2026-04-09

### Added

- Telegram bot with fail-secure authentication.
- Skills system (load, save, search, verify).
- Memory directories (contexto, decisiones, procedimientos, tecnologia).

---

## [0.3.0] - 2026-04-08

### Added

- BashTool, FileReadTool, FileWriteTool, FileEditTool, WebFetchTool.
- SQLite WAL session store.
- Session tools (list, load, search).

---

## [0.2.0] - 2026-04-07

### Added

- Multi-provider support (primary/fallback/local).
- httpx SSE streaming.
- OpenAI-compatible endpoint integration.

---

## [0.1.0] - 2026-04-06

### Added

- Basic Textual TUI.
- Agent with agentic loop.
- Tool call handling.
- B-KODE.md project instructions.
