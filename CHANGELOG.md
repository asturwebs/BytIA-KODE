# Changelog

## [0.7.8] - 2026-04-30

### Fixed

- **BashTool allowlist incompleta**: Añadidos `rg` (ripgrep), `bat`, `eza`, `tokei`, `shellcheck` a `_DEFAULT_BINARIES`. Antes, el agente recurría a `python -c` como workaround. Binarios `z`, `tmux`, `gh` excluidos deliberadamente (sin valor para agente no-interactivo o superficie de seguridad excesiva).
- **Race condition en kill()**: `_active_subprocess` capturado en variable local antes del check de `returncode`. Elimina ventana teórica donde el callback `on_subprocess` podría sobrescribir la referencia durante terminate/kill.

### Added

- **Test: system message preservation**: Verifica que mensajes `role="system"` en cualquier posición de `self.messages` sobreviven a `_manage_context()`. El enforcement ya existía (filtro `non_system` en `agent.py:538`), pero el test protege contra regresiones futuras. 145 tests total.
- **Session metadata persistence**: `update_metadata()` en `SessionStore` persiste `model` y `token_count` por sesión. Hook en `Agent.chat()` actualiza ambos campos tras cada turno. SQL parametrizado con allowlist de campos.
- **Code review document**: `docs/CODE-REVIEW.md` con análisis triple (Hermes + Peke + Claude). 11 patrones buenos, 5 flags analizados, priorización para v0.7.8.

### Changed

- **ROADMAP.md**: Corregido allowlist marcada como completada cuando no lo estaba, binarios sin valor eliminados, threshold arbitrario TUI eliminado, cabecera actualizada.
- **CODE-REVIEW.md**: Flag #5 corregido (no era bug, enforcement existía), idiomas mezclados corregidos, tamaño TUI precisado.

## [0.7.7] - 2026-04-29

### Fixed

- **Tool Error Memory hash normalization**: `_get_tool_error_key()` now hashes only the `command` field (bash) or `path` field (file_write/file_edit) instead of the full JSON arguments. Previously, same command with different `workdir`/`timeout` produced different hashes, bypassing the error memory and allowing repeated blocked commands.
- **BashTool allowlist missing `df`**: Added `df` to `_DEFAULT_BINARIES` for disk diagnostics. Previously required `python -c` workarounds.
- **BashTool allowlist missing `du`, `head`, `tail`**: Added read-only diagnostic/filtering binaries. `du` for disk usage, `head`/`tail` for file inspection.
- **BashTool error messages lack hints**: Binary rejection messages now include the list of allowed commands and contextual hints (e.g., `cd` → "use workdir parameter"). Reduces agent retry loops from 7+ to 1.
- **Flaky test `test_file_write_tool_handles_relative_path`**: Test now calls `set_workspace_root()` to reset the global `_WORKSPACE_ROOT`, preventing contamination from earlier tests.
- **pytest `testpaths` missing**: Added `[tool.pytest.ini_options]` with `testpaths = ["tests", "src/tests"]`. Previously `uv run pytest -q` collected only 116 of 142 tests.

### Added

- **2 tests**: `test_error_memory_hashes_command_only` (hash stability with different workdir), `test_error_memory_blocks_security_policy_rejections` (pipe/chain commands remembered). Total: 144.

## [0.7.6] - 2026-04-29

### Fixed

- **YAML multiline description parser**: `_parse_skill()` now correctly handles `description: >` folded scalars by accumulating indented continuation lines. Previously, descriptions using agentskills.io format resulted in literal `>` string.
- **sync-vendor-skills.sh Python heredoc**: Script passed arguments via `python3 - "$args" << 'PYEOF'` instead of bare heredoc without sys.argv.
- **Secret scanner false positive**: Added `src/bytia_kode/vendor/skills/` to skip dirs (MCP tool names trigger 30-char entropy check).

### Added

- **FIX-3: Tool Error Memory** — `_tool_error_memory` dict (previously declared but unused) now stores MD5 hashes of rejected bash/file_write/file_edit arguments. Same command is skipped with `[blocked]` message on retry. Safe tools (file_read, grep) are not tracked.
- **FIX-4: Workspace Context Awareness** — `_workspace_context_block()` injects CWD, sandbox constraints, and trusted paths into the dynamic system prompt so the agent knows its boundaries before attempting operations.
- **sync-vendor-skills.sh** — New script that syncs skills from `~/bytia/skills/` to vendor/ with automatic agentskills.io → flat format transformation. Supports `--list`, `--sync`, and per-skill sync.
- **Vendor skills auto-update**: `_ensure_vendor_skills()` checks `.vendor-version` file and only reinstalls when package version changes.
- **9 tests**: 3 loader YAML multiline edge cases, 3 FIX-3 tool error memory, 3 FIX-4 workspace context.

### Changed

- **Vendor skills format**: Restored to flat format after agentskills.io sync corruption. All 4 vendor skills (bytia-constitution, bytia-memory, graphify, skills-manager) now use flat frontmatter compatible with KODE parser.

## [0.7.5] - 2026-04-29

### Changed

- **Skills System Architecture**: Migrated from flat `~/.bytia-kode/skills/` to layered structure with vendor/user/bytia priorities. Skills are now organized in layers: `bytia/` (ecosystem, highest priority) → `user/` (custom, writable) → `vendor/` (bundled, lowest priority).

### Added

- **Vendor Skills**: Core skills (bytia-constitution, bytia-memory, skills-manager, graphify) are now bundled in `src/bytia_kode/vendor/skills/` and installed automatically.
- **SkillLoader Layer Support**: `SkillLoader` now supports layered directory scanning with priority-based override (bytia > user > vendor).
- **Auto-installation of Vendor Skills**: `AppConfig._ensure_vendor_skills()` copies vendor skills on first run or update.
- **install.sh BytIA Integration**: Installer detects `~/bytia/` ecosystem and offers to create symlink for shared skills.
- **`get_skill_info()`**: New method to inspect loaded skills and layers.

### Fixed

- **SKILL.md Constant**: Corrected typo `SKILL_FILE = "SKILL_FILE"` → `SKILL_FILE = "SKILL.md"`.

### Security

- **Vendor skills are read-only**: User cannot modify vendor skills directly. Verification copies to user layer first.

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
