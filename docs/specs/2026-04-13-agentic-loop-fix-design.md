# Fix: Agentic Loop Infinite Restart Bug

**Date:** 2026-04-13
**Status:** Approved & Implemented
**Scope:** `src/bytia_kode/agent.py` — `Agent.chat()` method

## Problem

The `for...else: continue` pattern in `Agent.chat()` (line 452-453) causes an infinite agentic loop. When the streaming response completes normally (no user cancellation), the `else` clause fires `continue` on the outer loop, which:

1. **Never appends** the assistant response to `self.messages`
2. **Never processes** tool calls
3. **Never persists** the response to the session store
4. Calls the model again with the **same message history** (missing the assistant response)
5. Repeats up to 50 iterations (`max_iterations`)

### Evidence

Session database (`~/.bytia-kode/sessions.db`) shows sessions with extreme message counts:

| Session | Messages | Pattern |
|---------|----------|---------|
| `telegram_af892b35` | 146 | Same user prompt repeated 7+ times |
| `tui_4359ce59` | 123 | Same user prompt repeated 5+ times |
| `tui_5a907f2c` | 102 | Infinite loop |
| `tui_206f790d` | 85 | Infinite loop |

Both TUI and Telegram are affected (both use the same `Agent.chat()`).

### Root Cause

Python's `for...else` construct: the `else` block runs when the loop completes **without** a `break`. The `continue` in the `else` clause skips all post-stream processing (message storage, tool call handling) and restarts the outer iteration loop.

```python
# BUGGY CODE
async for chunk_type, data in provider_client.chat_stream(...):
    if self._cancel_event.is_set():
        break
    # accumulate chunks...
else:
    continue  # <-- fires on normal completion, skips everything below

# This code only runs if inner loop was broken (cancelled)
msg_count_before = len(self.messages)
# ... append message, persist, handle tool calls ...
```

## Solution

Remove the `else: continue` and add explicit cancellation handling after the stream completes. The post-stream code (message storage, tool call processing) **always** executes.

```python
# FIXED CODE
async for chunk_type, data in provider_client.chat_stream(...):
    if self._cancel_event.is_set():
        break
    # accumulate chunks...

# On cancellation: save partial response and exit
if self._cancel_event.is_set():
    if response_text or reasoning_text:
        stored_content = ...
        self.messages.append(Message(role="assistant", content=stored_content))
        # persist to session store
    break

# This code ALWAYS executes after stream completes
msg_count_before = len(self.messages)
# ... append message, persist, handle tool calls ...
```

### Changes Summary

| File | Change |
|------|--------|
| `src/bytia_kode/agent.py` | Remove `else: continue`, add cancellation guard after stream |
| `CHANGELOG.md` | Add bugfix entry |
| `DEVLOG.md` | Add session entry |
| `README.md` | Update test count if new tests added |

### What Does NOT Change

- System prompt construction
- Tool registry
- Session store
- Provider client
- TUI interface
- Telegram bot
- Any other module

## Testing

- Existing 106 tests must pass
- Add specific test for the loop termination behavior
