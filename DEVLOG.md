# BytIA KODE - Development Log

## Session 25 — 2026-04-17 — B-KODE.md Rewrite + Security Hardening

**Scope:** Complete rewrite of agent initialization docs, security audit of public repo, and intercom reorganization.

### B-KODE.md Rewrite

Previous B-KODE.md (71 lines, ~15% coverage) was missing critical information for Kode agent initialization:
- **2 errors:** documented non-existent `memory_store/search/index/read` tools; intercom Claw path was oversimplified
- **9 missing sections:** identity YAML system, 11 registered tools, bash allowlist, circuit breaker, streaming protocol, sessions SQLite WAL, TUI commands/keybindings, Telegram commands, audio/TTS, env variables

Rewrote to ~180 lines (~90% coverage). All 11 tools documented, identity two-layer architecture explained, 17 env vars with defaults.

Also updated CLAUDE.md with 13 non-obvious gotchas from DEVLOG and claude-mem investigation (reasoning leak fix, circuit breaker recovery, dev wrapper vs uv tool install, B-KODE.md walk-up gotcha, symlink sync, etc.).

### Security Audit — Public Repo Cleanup

Audited entire repo for private data exposure:
- **Removed:** 4 hardcoded `/home/asturwebs/` paths in B-KODE.md
- **Removed:** VPS IP `46.224.65.42` and SSH port from intercom section
- **Removed:** `.claude/settings.local.json` from git tracking (added to .gitignore)
- **Generalized:** paths in `docs/PLAN-memory-manager-B-KODE.md` and `docs/superpowers/plans/2026-04-15-circuit-breaker.md`
- **Created:** `SECURITY.md` with reporting policy, response timeline, security model documentation

### Dependabot Patches

- pytest 9.0.2 → 9.0.3 (tmpdir vulnerability)
- cryptography 46.0.6 → 46.0.7 (buffer overflow)
- Dismissed diskcache alert (false positive — not a dependency)

### GitHub Issues

- **Closed #1** (Panic Buttons) — feature complete since v0.6.0, remaining edge cases moved to #3
- **Opened #3** — Telegram /stop handler, AgentCancelledError, cancel tests

### Intercom Reorganization

Moved `~/bytia-intercom/` → `~/.bytia-kode/intercom/`:
- Kode can now access intercom via existing trusted path (`~/.bytia-kode/`)
- Updated 6 scripts (send, check, read, ack, notify, sync) with new default paths
- Updated `agent-intercom` SKILL.md (7 path references)
- Historical messages in sent/ and inbox/ preserved as-is (M09: immutability)
- Added Intercom Skill Package to ROADMAP v0.8.0

### Commits (4)

| Commit | Description |
|--------|-------------|
| `bf29afa` | docs: rewrite B-KODE.md with complete agent initialization data |
| `dd7eacd` | fix: remove private paths and VPS IP from public repo |
| `86420cd` | docs: add SECURITY.md with reporting policy and security model |
| `016687a` | fix: patch Dependabot alerts — pytest 9.0.3, cryptography 46.0.7 |

### Agents Used

3 parallel investigation agents: claude-mem search (42 observations), DEVLOG/ROADMAP/docs analysis, B-KODE.md audit against codebase.

## Session 24 — 2026-04-15 — Circuit Breaker Hardening (v0.7.1)

**Scope:** Fix 5 bugs found during live TUI testing of circuit breaker + fallback system.

### Context

Session 23 (v0.7.0) introduced circuit breaker with auto-fallback. Live testing revealed multiple issues in the fallback path, TUI signaling, and message storage.

### Issues Found & Fixed

| # | Issue | Root Cause | Fix |
|---|-------|-----------|-----|
| 1 | `<reasoning>` tags leaking into model output | `agent.py` stored reasoning wrapped in `<reasoning>` tags in message history → sent back to model on next turn | Strip reasoning from stored content entirely. Only `response_text` persists. |
| 2 | `[razonamiento sin respuesta de texto]` appearing in output | Hardcoded Spanish fallback string stored in messages | Replaced with `(sin respuesta de texto)` — no XML tags |
| 3 | Security bypass: model wrote `_cleanup.py` + `python _cleanup.py` | `rmdir` not in BashTool allowlist → model found workaround via file_write + bash python | Added `rmdir` to `_DEFAULT_BINARIES` |
| 4 | No fallback notification in console | `yield ("provider_used", ...)` only emitted BEFORE the for-loop. Exception handler's `continue` skipped it. | Added `yield ("provider_used", provider)` in exception handler before `continue` |
| 5 | Circuit breaker never recovers to primary | `get_healthy(preferred)` prioritized `preferred` (which was "fallback" after switch) → primary never retried even after HALF_OPEN recovery | Refactored `get_healthy()` to always walk full priority order from top. Primary gets retried via HALF_OPEN naturally. |

### Additional Fixes

- **Duplicate watcher message:** Removed `_add_system_message()` from `_on_provider_changed` watcher — notification now comes exclusively from `provider_used` chunk handler. Avoids duplicate messages.
- **Stale `uv tool` install:** Removed `bytia-kode v0.5.3` from `~/.local/share/uv/tools/`. Replaced with wrapper script pointing to project's editable `.venv`.

### Files Modified

- `src/bytia_kode/agent.py` — reasoning storage cleanup + provider_used yield in fallback path
- `src/bytia_kode/providers/manager.py` — get_healthy() priority order refactor
- `src/bytia_kode/tools/registry.py` — `rmdir` added to allowlist
- `src/bytia_kode/tui.py` — provider_used handler + system message + watcher dedup
- `tests/test_agentic_loop.py` — updated assertions for new reasoning storage behavior

### Test Results

```
130 passed in 1.50s
```

### Commits

| Commit | Description |
|--------|-------------|
| `3f77925` | fix: update status line when circuit breaker switches provider |
| `9b13639` | fix: eliminate recursive chat() call, use loop-continue for provider fallback |
| `4320b07` | fix: auto-fallback to next provider when router is down at startup |
| `e9532bf` | fix: update status line when circuit breaker switches provider |
| `ac25666` | fix: circuit breaker hardening — reasoning leak, fallback signaling, recovery (v0.7.1) |

### Live Test Session

- **Session:** `tui_dc55ec40` (33 messages)
- **Router OFF → ON cycling** — fallback notification, status line updates, circuit recovery all confirmed working
- **Known model issue:** Gemma 4 26B entered reasoning loop (9804 chars) without executing actions — model behavior, not KODE bug

---

## Session 23 — 2026-04-15 — Circuit Breaker (v0.7.0)

### Commits (7)

| Commit | Description |
|--------|-------------|
| `a55ae72` | feat: add CircuitBreaker class with state transitions and recovery |
| `3615630` | feat: ProviderManager circuit breaker integration with get_healthy() |
| `e237a21` | feat: Agent automatic provider fallback with circuit breaker |
| `c2c27d6` | feat: TUI and Telegram system messages for provider fallback |
| `4a6520c` | docs: v0.7.0 release — circuit breaker for provider auto-fallback |
| `ee65747` | docs: comprehensive documentation audit and update for v0.7.0 |
| `1338f4b` | fix: correct ARCHITECTURE.md tool list and binary allowlist |

### Key Architecture Changes

- **CircuitBreaker** (`providers/circuit.py`): CLOSED/OPEN/HALF_OPEN states, 3-failure threshold, 60s recovery timeout
- **ProviderManager.get_healthy()**: walks priority order, returns first available circuit
- **Agent.chat()**: `force_open()` on primary when router unreachable at init, loop-internal fallback via `continue`
- **TUI**: system messages on provider switch, ActivityIndicator refresh on change

### Testing

- 130 tests (2 new circuit breaker tests + test mocks updated for `get_healthy()`)
- Live testing confirmed basic fallback flow

---

## Session 22 — 2026-04-12 — Reasoning Persistence & Docs (v0.6.1)

### Commits (5)

| Commit | Description |
|--------|-------------|
| `750fc25` | feat: persist reasoning in session + 5 tests for assistant persistence |
| `24d3ceb` | docs: update CHANGELOG, DEVLOG, README with reasoning persistence + 106 tests |
| `b136e7d` | fix: eliminate agentic loop infinite restart (v0.6.1) |
| `83c8519` | fix: ToolRegistry.execute() accepts on_subprocess from Agent (v0.6.1) |
| `dd29143` | Update test count from 92 to 112 in DEVLOG.md |

---

## Session 21 — 2026-04-11 — Panic Buttons & Native Tools (v0.6.0)

### Features

- **Panic Buttons**: Escape (interrupt) + Ctrl+K (kill agent) — two-level cancellation
- **Native exploration tools**: GrepTool, GlobTool, TreeTool — Python-native, no bash dependency
- **Sandbox fix**: `_validate_command_safety()` blocks shell operators
- **Reasoning persistence**: assistant messages store reasoning for context continuity
- **106 tests** passing

---

## Session 20 — 2026-04-10 — TUI Themes & Polish (v0.5.0)

- 19 TUI themes via CSS
- Streaming rendering with RichMarkdown
- ThinkingBlock collapsible reasoning
- ToolBlock with color-coded output
- Session management (/sessions, /load, /new)

---

## Session 19 — 2026-04-09 — Telegram Bot & Skills (v0.4.0)

- Telegram bot with fail-secure auth
- Skills system (load, save, search, verify)
- Memory directories (contexto, decisiones, procedimientos, tecnologia)

---

## Session 18 — 2026-04-08 — Tools & Session Persistence (v0.3.0)

- BashTool, FileReadTool, FileWriteTool, FileEditTool, WebFetchTool
- SQLite WAL session store
- Session tools (list, load, search)

---

## Session 17 — 2026-04-07 — Provider System (v0.2.0)

- Multi-provider support (primary/fallback/local)
- httpx SSE streaming
- OpenAI-compatible chat/completions endpoint

---

## Session 16 — 2026-04-06 — Initial Agent (v0.1.0)

- Basic Textual TUI
- Agent with agentic loop
- Tool call handling
- B-KODE.md project instructions
