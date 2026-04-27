# BytIA KODE - Development Log

## Session 29 — 2026-04-27 — Agent Loop Optimizations (v0.7.3)

**Scope:** Performance and reliability improvements to the agentic loop based on session audit (22-iteration trace). Four quick wins implemented.

### Changes

| # | What | Impact |
|---|---|---|
| 1 | **SP cache** — `_build_system_prompt()` cached per message count, invalidated on identity change | Saves 1 full SP rebuild per iteration (~500ms/iter for 22-iter loop = ~11s saved) |
| 2 | **Router polling paused** — `_poll_router_info()` returns early when `is_processing` | Eliminates 12-24 unnecessary HTTP requests during long generations |
| 3 | **Better placeholder** — `reasoning_text[:200]` as fallback instead of literal `(sin respuesta de texto)` | Less history pollution when model generates only reasoning |
| 4 | **Batch context compression** — 5 messages at once instead of 2, last 4 always preserved, truncation for old history | Fewer LLM calls during compression; ~5× faster when context overflows |

### Files Changed

| File | Changes |
|---|---|
| `agent.py` | SP cache (+16 lines), better placeholder (1 line), batch compression (+15/-12 lines) |
| `tui.py` | Router poll pause (2 lines) |
| `tests/test_agentic_loop.py` | Updated assertion for new placeholder |
| `tests/test_context_management.py` | Updated assertions for batch compression |

### Tests

110 passed — no regressions.

---

## Session 28 — 2026-04-27 — Structured CoT Grammar Exploration (reverted)

**Scope:** Full exploration of GBNF grammar-constrained Chain-of-Thought for B-KODE. Inspired by `andthattoo/structured-cot` (22× thinking token compression). Integrated, tested, and ultimately **reverted** — incompatible with agentic tool use.

### What We Built & Reverted

- 4 GBNF grammars (base, enriched, P22, P20 protocols)
- `ProviderClient.supports_grammar` property
- `grammar` parameter in `chat()`/`chat_stream()` payloads
- Agent: lazy loading, toggle, 2-pass grammar+tools approach
- TUI: `/grammar` command, `Ctrl+G`, `[G]` indicator
- 18 grammar tests
- Full v0.7.3 release published to GitHub

### What Stayed

| Component | Why |
|---|---|
| `supports_grammar` on `ProviderClient` | Provider capability detection pattern, zero overhead |
| `llama-update.sh` | Engine auto-update with weekly cron |
| llama.cpp b8946 | 98 commits of improvements (grammar/autoparser/CUDA fixes) |
| check_secrets skip patterns | `reasoning_content` + `.gbnf` patterns, less false positives |
| git tag b8944→b8946 backup | Fast rollback if needed |

### Root Cause: Why Grammar Failed

1. **llama-server rejects grammar+tools in same request** — hard limitation, documented in source: "Cannot use custom grammar constraints with tools"
2. **2-pass approach breaks** — grammar iteration stores assistant message with `reasoning_content`; next iteration with tools triggers "prefill incompatible with enable_thinking" (400)
3. **Without tools, agent hallucinates** — model writes pseudo tool calls as text instead of executing real ones
4. **Grammar sampler inhibited during reasoning** (fix #20970 in llama.cpp) — reasoning is free-form even with grammar, only content is constrained

### Key Findings

- GBNF grammar works perfectly for **non-agentic** generation (direct LLM calls without tools)
- The structured-cot paper tested on HumanEval+/LiveCodeBench — pure code generation, zero tool use
- Grammar reduces thinking tokens ~22× on supported benchmarks, but at 118 t/s on local RTX 4090 this is irrelevant — 25s vs 1.2s saving
- The `reasoning-format=deepseek` + grammar interaction is complex: grammar applies to raw output, server splits into reasoning/content channels
- `supports_grammar` detection pattern is valuable infrastructure for future provider capability checks

### Reference

- Paper: `andthattoo/structured-cot` — https://github.com/andthattoo/structured-cot
- llama.cpp PR #20223/#20970 — grammar sampler inhibited during reasoning
- llama.cpp PR #21870 — reasoning budget skip when no budget
- Our analysis doc was in `docs/structured-cot-analysis.md` (deleted with revert)

### Files Net Change

v0.7.2 → v0.7.3 → v0.7.2: 0 net lines (full revert)
Kept: `supports_grammar` (+12 lines client.py), check_secrets patterns (+3 lines)

---

## Session 27 — 2026-04-26 — DeepSeek reasoning_content Fix (v0.7.2)

**Scope:** Fix DeepSeek 400 Bad Request when tool calls follow reasoning. Store and re-send `reasoning_content` per DeepSeek API requirement.

### Problem

DeepSeek's API requires that when an assistant message contains `reasoning_content` and `tool_calls`, the `reasoning_content` must be passed back in all subsequent requests. B-KODE was discarding `reasoning_content` after streaming, causing 400 errors on the next turn whenever DeepSeek used tools after reasoning.

### Root Cause

Three gaps in the message pipeline:
1. **`ProviderResponse`**: No `reasoning_content` field — parsed from stream but discarded after yield
2. **`Message`**: No `reasoning_content` field — agent accumulated `reasoning_text` but never stored it
3. **`SessionStore`**: No `reasoning_content` column — not persisted, lost on session reload

### Fix

| File | Change |
|------|--------|
| `providers/client.py` | `Message` + `ProviderResponse` get `reasoning_content: str \| None = None`. `chat()` extracts it from response JSON. |
| `agent.py` | `reasoning_text` stored in `Message.reasoning_content`. Persisted to session via `append_message`. Loaded on session restore via `_load_messages_from_store`. |
| `session.py` | Schema: `reasoning_content TEXT DEFAULT NULL` column. `ALTER TABLE ADD COLUMN` migration for existing DBs. `append_message` / `load_messages` updated. |

### Design Decisions

- **`exclude_none=True` compatibility**: `Message.model_dump(exclude_none=True)` only serializes `reasoning_content` when it has a value. Non-DeepSeek providers never see the field.
- **Silent ALTER TABLE**: Migration wrapped in try/except — existing databases get the new column automatically, new databases get it from schema.
- **No TUI changes**: `reasoning_content` is transparent to the TUI. It's already yielding `("reasoning", data)` chunks for display in ThinkingBlock. The change only affects what gets stored and sent back to the API.

### Testing

- 130 passed — no regressions
- Live test in TUI: DeepSeek (deepseek-v4-flash) with 4 tool calls + 13 lines of reasoning, no 400 errors

### Files Changed

| File | Change |
|------|--------|
| `src/bytia_kode/providers/client.py` | +`reasoning_content` field on `Message` and `ProviderResponse` + extraction in `chat()` |
| `src/bytia_kode/agent.py` | Store `reasoning_to_store` in `Message` + persist to session + load from session |
| `src/bytia_kode/session.py` | Schema column + ALTER TABLE migration + `append_message`/`load_messages` updated |
| `pyproject.toml` | Version bump 0.7.1 → 0.7.2 |
| `CHANGELOG.md` | Added reasoning_content fix to [0.7.2] |

---

## Session 26 — 2026-04-26 — DeepSeek Provider + Sticky Pinning + Claude Code Multi-Provider

**Scope:** DeepSeek V4 integration in B-KODE and Claude Code, provider pinning architecture, context-aware switching, settings.json model override fix.

### DeepSeek V4 Provider (B-KODE)

Added DeepSeek as 5th provider slot in ProviderManager with OpenAI-compatible endpoint:

- **config.py**: 4 new fields — `deepseek_url`, `deepseek_key`, `deepseek_model`, `deepseek_max_context` (default 1M tokens)
- **manager.py**: New `deepseek` slot, circuit breaker, priority 4 (primary → fallback → minimax → deepseek → local)
- **tui.py**: DeepSeek row in `/model` table (was hardcoded, missing new provider), display name in `_provider_display_name`
- **.env / .env.example**: `DEEPSEEK_BASE_URL`, `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL=deepseek-v4-flash`, `DEEPSEEK_MAX_CONTEXT=1000000`

DeepSeek API docs reviewed:
- OpenAI-compatible: `https://api.deepseek.com` (B-KODE uses this)
- Anthropic-compatible: `https://api.deepseek.com/anthropic` (Claude Code uses this)
- Models: `deepseek-v4-flash` (fast, 284B/13B MoE), `deepseek-v4-pro` (thinking, 1.6T/49B)
- Thinking mode: `reasoning_effort` param + `thinking: {type: "enabled"}` in OpenAI format
- `[1m]` suffix for thinking budget only applies to Anthropic endpoint

### Provider Pinning (Sticky)

Implemented manual provider selection that sticks until user changes it:

- **`ProviderManager._pinned`**: When user presses F3 to switch provider, it gets pinned
- **`get_healthy()`**: If pinned, always returns pinned provider (ignores circuit state). No auto-fallback on failure.
- **`agent.py`**: If pinned provider fails, yields error and stops — doesn't auto-switch. Only auto-fallbacks when NOT pinned (original behavior preserved).
- **Rationale**: User is always at the terminal for now. Auto-fallback to dead primary was worse than showing the error. Circuit breaker auto-recovery stays in roadmap for v0.8 (unattended agents).

### Context-Aware Provider Switching

Each provider now properly sets context limit on switch:

- **`_on_provider_changed()`**: On F3 switch, calls `update_context_limit()` with provider-specific value
- **`get_context_limit()`**: DeepSeek = configurable via `DEEPSEEK_MAX_CONTEXT` (default 1M). Others = agent default (262k). Primary = 0 (router polling handles it, 5s interval)
- **Import**: Added `MAX_CONTEXT_TOKENS` to tui.py imports from agent.py
- **Fixes**: Context no longer stays at 1M when switching from DeepSeek back to Z.ai; no longer shows stale router ctx (131k) when on cloud provider

### Claude Code Multi-Provider Setup

Added `claude-ds` alias and fixed model override conflicts:

- **`.zshrc.secrets`**: `DEEPSEEK_API_KEY` added
- **`.zshrc`**: `claude-ds()` function with Anthropic-compatible endpoint, `deepseek-v4-pro[1m]` for Opus/Sonnet, `deepseek-v4-flash` for Haiku/Subagent, `CLAUDE_CODE_EFFORT_LEVEL=max`
- **settings.json fix**: Removed `ANTHROPIC_DEFAULT_{SONNET,OPUS,HAIKU}_MODEL` GLM overrides. These were overriding process env vars from aliases (settings.json env > process env vars in Claude Code). Moved GLM models to `claude-zai` and `claude-zai-yolo` aliases explicitly.
- **`.bytia-banner`**: Added `claude-ds` line in CLIs section

### Files Changed

| File | Change |
|------|--------|
| `src/bytia_kode/config.py` | +4 DeepSeek fields |
| `src/bytia_kode/providers/manager.py` | DeepSeek slot + `_pinned` + sticky `get_healthy()` + `get_context_limit()` |
| `src/bytia_kode/agent.py` | Pin-aware error handling (pinned → stop, not pinned → auto-fallback) |
| `src/bytia_kode/tui.py` | `/model` table + display name + pin/unpin + ctx reset on switch + `MAX_CONTEXT_TOKENS` import |
| `.env` | DeepSeek config (4 vars) |
| `.env.example` | DeepSeek template |
| `~/.zshrc` | `claude-ds`, updated `claude-zai`/`claude-zai-yolo` with GLM model vars |
| `~/.zshrc.secrets` | `DEEPSEEK_API_KEY` |
| `~/.claude/settings.json` | Removed 3 model overrides |
| `~/.bytia-banner` | `claude-ds` line |

### Tests

130 passed — no regressions. All existing circuit breaker and fallback tests continue to pass with original (non-pinned) behavior.

### Roadmap Items (Deferred to v0.8)

- **Smart circuit breaker**: When pinned provider fails, auto-fallback to next healthy provider instead of stopping (for unattended agent sessions)
- **Session event log**: Store tool calls, bash commands, provider/model/theme changes in session as structured events (current: only user input + model output)

---

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
