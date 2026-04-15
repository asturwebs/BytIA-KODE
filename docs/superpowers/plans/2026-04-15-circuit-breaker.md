# Circuit Breaker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automatic provider fallback with circuit breaker pattern so the agent transparently switches to an alternate provider when the primary fails.

**Architecture:** Each provider gets a `CircuitBreaker` instance with 3 states (CLOSED/OPEN/HALF_OPEN). `ProviderManager.get_healthy()` returns the first available provider. `Agent.chat()` uses `get_healthy()` instead of `get()`, yields `("system", ...)` on provider switch, and reports success/failure back to the circuit breakers.

**Tech Stack:** Python stdlib (`time.monotonic`), no new dependencies. Tests with `pytest`, `pytest-asyncio`, `unittest.mock`.

---

### Task 1: CircuitBreaker class — Unit Tests

**Files:**
- Create: `tests/test_circuit_breaker.py`

- [ ] **Step 1: Write all CircuitBreaker tests**

```python
"""Tests for CircuitBreaker — state transitions and recovery logic."""
import time

import pytest

from bytia_kode.providers.circuit import CircuitBreaker


class TestCircuitBreakerStates:
    def test_starts_closed(self):
        cb = CircuitBreaker()
        assert cb.state == "closed"

    def test_success_keeps_closed(self):
        cb = CircuitBreaker()
        cb.record_success()
        assert cb.state == "closed"
        assert cb.is_available is True

    def test_failures_open_circuit(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        assert cb.state == "closed"
        cb.record_failure()
        assert cb.state == "closed"
        cb.record_failure()
        assert cb.state == "open"
        assert cb.is_available is False

    def test_failure_count_resets_on_success(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"  # Only 2 failures after reset

    def test_recovery_to_half_open(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        assert cb.state == "open"
        time.sleep(0.02)
        assert cb.is_available is True
        assert cb.state == "half_open"

    def test_half_open_success_closes(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        assert cb.state == "open"
        time.sleep(0.02)
        _ = cb.is_available  # triggers recovery
        assert cb.state == "half_open"
        cb.record_success()
        assert cb.state == "closed"
        assert cb.is_available is True

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        assert cb.state == "open"
        time.sleep(0.02)
        _ = cb.is_available  # triggers recovery
        assert cb.state == "half_open"
        cb.record_failure()
        assert cb.state == "open"
        assert cb.is_available is False

    def test_open_is_not_available_before_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()
        assert cb.state == "open"
        assert cb.is_available is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/asturwebs/bytia/proyectos/BytIA-KODE && uv run pytest tests/test_circuit_breaker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bytia_kode.providers.circuit'`

---

### Task 2: CircuitBreaker class — Implementation

**Files:**
- Create: `src/bytia_kode/providers/circuit.py`

- [ ] **Step 3: Write CircuitBreaker implementation**

```python
"""Circuit breaker for provider resilience."""
from __future__ import annotations

import time


class CircuitBreaker:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 60.0):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failure_count: int = 0
        self._state: str = self.CLOSED
        self._last_failure_time: float = 0.0

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_available(self) -> bool:
        if self._state == self.CLOSED:
            return True
        if self._state == self.OPEN:
            if time.monotonic() - self._last_failure_time >= self._recovery_timeout:
                self._state = self.HALF_OPEN
                return True
            return False
        if self._state == self.HALF_OPEN:
            return True
        return False

    def record_success(self) -> None:
        self._failure_count = 0
        if self._state == self.HALF_OPEN:
            self._state = self.CLOSED

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._state == self.HALF_OPEN:
            self._state = self.OPEN
        elif self._failure_count >= self._failure_threshold:
            self._state = self.OPEN
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/asturwebs/bytia/proyectos/BytIA-KODE && uv run pytest tests/test_circuit_breaker.py -v`
Expected: 8 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/asturwebs/bytia/proyectos/BytIA-KODE
git add src/bytia_kode/providers/circuit.py tests/test_circuit_breaker.py
git commit -m "feat: add CircuitBreaker class with state transitions and recovery"
```

---

### Task 3: ProviderManager — get_healthy() and circuit integration tests

**Files:**
- Create: `tests/test_provider_health.py`

- [ ] **Step 6: Write ProviderManager health tests**

```python
"""Tests for ProviderManager health tracking and get_healthy()."""
import pytest
from unittest.mock import MagicMock

from bytia_kode.providers.circuit import CircuitBreaker
from bytia_kode.providers.manager import ProviderManager


@pytest.fixture
def manager():
    cfg = MagicMock()
    cfg.base_url = "http://primary:8080/v1"
    cfg.api_key = "key1"
    cfg.model = "test-model"
    cfg.fallback_url = "http://fallback:8080/v1"
    cfg.fallback_key = "key2"
    cfg.fallback_model = "fallback-model"
    cfg.local_url = "http://local:11434/v1"
    cfg.local_model = "local-model"
    return ProviderManager(cfg)


class TestProviderManagerHealth:
    def test_get_healthy_returns_preferred_when_closed(self, manager):
        client, name = manager.get_healthy("primary")
        assert name == "primary"

    def test_get_healthy_skips_open_circuit(self, manager):
        manager._circuits["primary"].record_failure()
        manager._circuits["primary"].record_failure()
        manager._circuits["primary"].record_failure()
        assert manager._circuits["primary"].state == "open"
        client, name = manager.get_healthy("primary")
        assert name == "fallback"

    def test_get_healthy_all_open_returns_preferred(self, manager):
        for cb in manager._circuits.values():
            for _ in range(3):
                cb.record_failure()
        client, name = manager.get_healthy("primary")
        assert name == "primary"

    def test_report_success_resets_circuit(self, manager):
        manager._circuits["primary"].record_failure()
        manager._circuits["primary"].record_failure()
        assert manager._circuits["primary"].state == "closed"
        manager._circuits["primary"].record_failure()
        assert manager._circuits["primary"].state == "open"
        manager.report_success("primary")
        assert manager._circuits["primary"].state == "closed"

    def test_report_failure_increments(self, manager):
        assert manager._circuits["primary"].state == "closed"
        manager.report_failure("primary")
        manager.report_failure("primary")
        assert manager._circuits["primary"].state == "closed"
        manager.report_failure("primary")
        assert manager._circuits["primary"].state == "open"

    def test_list_available_excludes_open(self, manager):
        for _ in range(3):
            manager._circuits["primary"].record_failure()
        assert manager._circuits["primary"].state == "open"
        available = manager.list_available()
        assert "primary" not in available
        assert "fallback" in available

    def test_get_status_returns_all_circuits(self, manager):
        status = manager.get_status()
        assert "primary" in status
        assert status["primary"]["state"] == "closed"
        assert status["primary"]["failures"] == 0
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `cd /home/asturwebs/bytia/proyectos/BytIA-KODE && uv run pytest tests/test_provider_health.py -v`
Expected: FAIL — `AttributeError: 'ProviderManager' object has no attribute 'get_healthy'`

---

### Task 4: ProviderManager — Implementation

**Files:**
- Modify: `src/bytia_kode/providers/manager.py`

- [ ] **Step 8: Add circuit breaker integration to ProviderManager**

Add import at top of `manager.py`:

```python
from bytia_kode.providers.circuit import CircuitBreaker
```

Add to `__init__` after creating providers (after the `self._local` block):

```python
        self._circuits: dict[str, CircuitBreaker] = {"primary": CircuitBreaker()}
        if self._fallback:
            self._circuits["fallback"] = CircuitBreaker()
        if self._local:
            self._circuits["local"] = CircuitBreaker()
        self._priority_order = ["primary"]
        if self._fallback:
            self._priority_order.append("fallback")
        if self._local:
            self._priority_order.append("local")
```

Add new methods (after `set_model`):

```python
    def get_healthy(self, preferred: str = "primary") -> tuple[ProviderClient, str]:
        """Return (client, name) of first available provider.

        Order: preferred → rest by priority. If all OPEN → returns preferred as last resort.
        """
        preferred_cb = self._circuits.get(preferred)
        if preferred_cb and preferred_cb.is_available:
            return self.get(preferred), preferred

        for name in self._priority_order:
            if name == preferred:
                continue
            cb = self._circuits.get(name)
            if cb and cb.is_available:
                return self.get(name), name

        logger.warning("All providers in OPEN state — using %s as last resort", preferred)
        return self.get(preferred), preferred

    def report_success(self, provider: str) -> None:
        cb = self._circuits.get(provider)
        if cb:
            cb.record_success()

    def report_failure(self, provider: str) -> None:
        cb = self._circuits.get(provider)
        if cb:
            cb.record_failure()
            if cb.state == "open":
                logger.warning("Circuit OPEN for provider '%s'", provider)

    def get_status(self) -> dict[str, dict]:
        return {
            name: {"state": cb.state, "failures": cb._failure_count}
            for name, cb in self._circuits.items()
        }
```

Modify `list_available` to filter by circuit state:

```python
    def list_available(self) -> list[str]:
        """Return list of provider names with healthy circuits."""
        return [name for name in self._priority_order if self._circuits[name].is_available]
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd /home/asturwebs/bytia/proyectos/BytIA-KODE && uv run pytest tests/test_provider_health.py -v`
Expected: 8 tests PASS

- [ ] **Step 10: Run all existing tests to verify no regression**

Run: `cd /home/asturwebs/bytia/proyectos/BytIA-KODE && uv run pytest -v`
Expected: All 114 tests PASS (106 existing + 8 new circuit breaker)

- [ ] **Step 11: Commit**

```bash
cd /home/asturwebs/bytia/proyectos/BytIA-KODE
git add src/bytia_kode/providers/manager.py tests/test_provider_health.py
git commit -m "feat: ProviderManager circuit breaker integration with get_healthy()"
```

---

### Task 5: Agent — Fallback integration tests

**Files:**
- Modify: `tests/test_agentic_loop.py` (append tests)

- [ ] **Step 12: Write Agent fallback tests**

Append to `tests/test_agentic_loop.py`:

```python


class TestProviderFallback:
    """Verify automatic provider fallback when primary fails."""

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self, agent):
        """When primary fails, agent falls back to next available provider."""
        failing_provider = AsyncMock()
        failing_provider.chat_stream = _mock_stream_response(text="")
        failing_provider.chat_stream.side_effect = ConnectionError("Primary down")

        working_provider = AsyncMock()
        working_provider.chat_stream = _mock_stream_response(text="Fallback response.")

        agent.providers._primary = failing_provider
        agent.providers._fallback = working_provider
        agent.providers._circuits["primary"]._failure_threshold = 1

        agent.providers.get = MagicMock(side_effect=lambda name: {
            "primary": failing_provider,
            "fallback": working_provider,
        }[name])

        collected = []
        async for chunk in agent.chat("test"):
            collected.append(chunk)

        system_msgs = [c for c in collected if isinstance(c, tuple) and c[0] == "system"]
        assert len(system_msgs) >= 1
        assert "fallback" in system_msgs[0][1].lower()

    @pytest.mark.asyncio
    async def test_system_message_on_provider_switch(self, agent):
        """Agent yields ('system', msg) when switching providers."""
        failing_provider = AsyncMock()
        failing_provider.chat_stream = MagicMock(side_effect=ConnectionError("Down"))

        working_provider = AsyncMock()
        working_provider.chat_stream = _mock_stream_response(text="OK")

        agent.providers._primary = failing_provider
        agent.providers._fallback = working_provider
        agent.providers._circuits["primary"]._failure_threshold = 1

        agent.providers.get = MagicMock(side_effect=lambda name: {
            "primary": failing_provider,
            "fallback": working_provider,
        }[name])

        collected = []
        async for chunk in agent.chat("test"):
            collected.append(chunk)

        system_msgs = [c for c in collected if isinstance(c, tuple) and c[0] == "system"]
        assert any("fallback" in m[1].lower() for m in system_msgs)

    @pytest.mark.asyncio
    async def test_all_providers_fail_yields_error(self, agent):
        """When all providers fail, yields ('error', msg)."""
        failing = AsyncMock()
        failing.chat_stream = MagicMock(side_effect=ConnectionError("All down"))

        agent.providers._primary = failing
        agent.providers._fallback = failing
        agent.providers._local = failing
        for cb in agent.providers._circuits.values():
            cb._failure_threshold = 1

        agent.providers.get = MagicMock(return_value=failing)

        collected = []
        async for chunk in agent.chat("test"):
            collected.append(chunk)

        error_msgs = [c for c in collected if isinstance(c, tuple) and c[0] == "error"]
        assert len(error_msgs) >= 1
```

- [ ] **Step 13: Run tests to verify they fail**

Run: `cd /home/asturwebs/bytia/proyectos/BytIA-KODE && uv run pytest tests/test_agentic_loop.py::TestProviderFallback -v`
Expected: FAIL — Agent still uses `get()` not `get_healthy()`

---

### Task 6: Agent — Implementation

**Files:**
- Modify: `src/bytia_kode/agent.py`

- [ ] **Step 14: Modify `chat()` method to use circuit breaker**

In `agent.py`, find the `chat()` method. Locate this line (~line 310):

```python
        provider_client = self.providers.get(provider)
```

Replace with:

```python
        client, used_provider = self.providers.get_healthy(provider)
        if used_provider != provider:
            yield ("system", f"Provider '{provider}' no disponible. Usando '{used_provider}'.")
            provider = used_provider
        provider_client = client
```

Then find the error handling at the bottom of the `try` block (~line 375):

```python
        except (TimeoutError, ConnectionError, RuntimeError, httpx.HTTPError) as exc:
            error_message = _format_chat_error(exc)
            logger.error("Agent chat failure: %s", error_message)
            self.messages.append(Message(role="assistant", content=f"[Error: {error_message}]"))
            if self._current_session_id:
                self._session_store.append_message(
                    self._current_session_id, role="assistant", content=f"[Error: {error_message}]",
                )
            yield ("error", error_message)
```

Replace with:

```python
        except (TimeoutError, ConnectionError, RuntimeError, httpx.HTTPError) as exc:
            error_message = _format_chat_error(exc)
            logger.error("Agent chat failure on '%s': %s", provider, error_message)
            self.providers.report_failure(provider)
            remaining = [n for n in self.providers._priority_order if n != provider and self.providers._circuits.get(n, None) and self.providers._circuits[n].is_available]
            if remaining:
                next_provider = remaining[0]
                yield ("system", f"Provider '{provider}' falló. Intentando con '{next_provider}'...")
                self.messages = self.messages[:-1] if self.messages and self.messages[-1].role == "user" else self.messages
                async for chunk in self.chat(user_message, provider=next_provider):
                    yield chunk
                return
            self.messages.append(Message(role="assistant", content=f"[Error: {error_message}]"))
            if self._current_session_id:
                self._session_store.append_message(
                    self._current_session_id, role="assistant", content=f"[Error: {error_message}]",
                )
            yield ("error", error_message)
```

Also, find where the streaming succeeds (the `if not tool_calls_accum: break` line). Right before that break, add:

```python
                self.providers.report_success(provider)
```

So the code looks like:

```python
                if not tool_calls_accum:
                    self.providers.report_success(provider)
                    break
```

- [ ] **Step 15: Run fallback tests to verify they pass**

Run: `cd /home/asturwebs/bytia/proyectos/BytIA-KODE && uv run pytest tests/test_agentic_loop.py::TestProviderFallback -v`
Expected: 3 tests PASS

- [ ] **Step 16: Run all tests to verify no regression**

Run: `cd /home/asturwebs/bytia/proyectos/BytIA-KODE && uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 17: Commit**

```bash
cd /home/asturwebs/bytia/proyectos/BytIA-KODE
git add src/bytia_kode/agent.py tests/test_agentic_loop.py
git commit -m "feat: Agent automatic provider fallback with circuit breaker"
```

---

### Task 7: TUI and Telegram integration

**Files:**
- Modify: `src/bytia_kode/tui.py`
- Modify: `src/bytia_kode/telegram/bot.py`

- [ ] **Step 18: Add "system" case in TUI `_process_message()`**

In `tui.py`, find this block (around line 1003):

```python
                elif isinstance(chunk, tuple) and chunk[0] == "error":
                    if stream_widget and stream_widget.is_mounted:
                        stream_widget.remove()
                    self._add_message("error", chunk[1])
```

Insert BEFORE it:

```python
                elif isinstance(chunk, tuple) and chunk[0] == "system":
                    self._add_message("system", chunk[1])
```

- [ ] **Step 19: Add "system" case in Telegram bot**

In `telegram/bot.py`, find this block (around line 194):

```python
                if isinstance(chunk, tuple) and chunk[0] == "error":
                    await update.message.reply_text(f"⚠️ {chunk[1]}")
                    return
```

Insert BEFORE it:

```python
                if isinstance(chunk, tuple) and chunk[0] == "system":
                    await update.message.reply_text(f"ℹ️ {chunk[1]}")
                    continue
```

- [ ] **Step 20: Run all tests to verify no regression**

Run: `cd /home/asturwebs/bytia/proyectos/BytIA-KODE && uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 21: Commit**

```bash
cd /home/asturwebs/bytia/proyectos/BytIA-KODE
git add src/bytia_kode/tui.py src/bytia_kode/telegram/bot.py
git commit -m "feat: TUI and Telegram system messages for provider fallback"
```

---

### Task 8: Version bump and documentation

**Files:**
- Modify: `pyproject.toml`
- Modify: `ROADMAP.md`
- Modify: `CHANGELOG.md`
- Modify: `DEVLOG.md`

- [ ] **Step 22: Bump version in pyproject.toml**

In `pyproject.toml`, change `version = "0.6.1"` to `version = "0.7.0"`.

- [ ] **Step 23: Update ROADMAP.md**

In `ROADMAP.md`, find the `## v0.7.0` section. Replace the existing content with:

```markdown
## v0.7.0 — Circuit Breaker y Provider Resilience (COMPLETADO)

### Completado

- [x] **CircuitBreaker class** — CLOSED/OPEN/HALF_OPEN state machine con auto-recuperación
- [x] **ProviderManager.get_healthy()** — routing inteligente por prioridad con health check
- [x] **Agent auto-fallback** — si provider falla, intenta siguiente automáticamente
- [x] **System messages** — aviso al usuario cuando se cambia de provider (TUI + Telegram)
- [x] **report_success / report_failure** — feedback loop del agentic loop al circuit breaker
- [x] **17 tests nuevos** — 8 CircuitBreaker + 6 ProviderManager + 3 Agent fallback
```

- [ ] **Step 24: Update CHANGELOG.md**

Add entry at the top of `CHANGELOG.md`:

```markdown
## [0.7.0] - 2026-04-15

### Added
- Circuit Breaker pattern for provider auto-fallback (CLOSED → OPEN → HALF_OPEN)
- `providers/circuit.py` — new `CircuitBreaker` class with configurable threshold and recovery
- `ProviderManager.get_healthy()` — returns first available provider by priority
- `ProviderManager.report_success/failure()` — feedback loop for circuit state
- `ProviderManager.get_status()` — circuit state for debugging/UI
- `Agent.chat()` automatic fallback to next provider on failure
- System messages in TUI and Telegram when provider switches
- 17 new tests (8 CircuitBreaker + 6 ProviderManager + 3 Agent fallback)
```

- [ ] **Step 25: Add DEVLOG entry**

Append to `DEVLOG.md`:

```markdown

## 2026-04-15 - Sesión 26: Circuit Breaker y Provider Resilience (v0.7.0)

### Contexto

Implementación del patrón Circuit Breaker para que el agente pueda cambiar automáticamente de provider cuando el primario falla, sin intervención del usuario.

### Novedades

1. **CircuitBreaker** — Clase con 3 estados (CLOSED/OPEN/HALF_OPEN), threshold configurable (default: 3 fallos), auto-recuperación tras 60s.
2. **ProviderManager.get_healthy()** — Devuelve el primer provider disponible por prioridad (primary→fallback→local). Si todos están OPEN, devuelve el preferido como último recurso.
3. **Agent auto-fallback** — Si el provider falla durante `chat()`, se reporta el fallo al circuit breaker y se reintenta con el siguiente provider disponible.
4. **System messages** — TUI y Telegram muestran aviso informativo cuando se cambia de provider.

### Tests

- 17 tests nuevos: 8 unitarios CircuitBreaker + 6 ProviderManager health + 3 Agent fallback
- Total: 123 tests pasando
```

- [ ] **Step 26: Final full test run**

Run: `cd /home/asturwebs/bytia/proyectos/BytIA-KODE && uv run pytest -v`
Expected: All 123 tests PASS

- [ ] **Step 27: Commit version bump and docs**

```bash
cd /home/asturwebs/bytia/proyectos/BytIA-KODE
git add pyproject.toml ROADMAP.md CHANGELOG.md DEVLOG.md
git commit -m "docs: v0.7.0 release — circuit breaker for provider auto-fallback"
```
