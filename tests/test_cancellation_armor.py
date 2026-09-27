"""Blindaje de cancelación (AST-24) — los 5 escenarios del Panic Button.

Deriva de GitHub issue #3. El fix principal (handler /stop real + H1/H2 de
AST-17) ya está en producción; este archivo blinda:

  S1  interrupt mid-stream (corta la generación LLM en progreso)
  S2  interrupt mid-tool + kill durante bash (aborta el lote restante)
  S3  kill durante bash con subprocess activo (terminate → reap → escalate)
  S4  el mensaje cancelado se persiste en sesión (disco, no sólo memoria)
  S5  `_cancel_event` queda limpio al arrancar el turno siguiente (H1)

Sobre S5: kill() NO limpia el evento a propósito (invariante H2 en agent.py:
kill() puede retornar antes de que el loop observe el set() y limpiar ahí
perdería el kill). La limpieza real vive en H1: un clear() por turno al
entrar a chat(). El test exige exactamente eso — limpio al empezar el turno
siguiente, no al final de kill().
"""
import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bytia_kode.providers.client import Message
from bytia_kode.agent import Agent


@pytest.fixture
def agent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = MagicMock()
    cfg.provider = MagicMock()
    cfg.data_dir = tmp_path / "data"
    cfg.skills_dir = Path(tmp_path / "skills")
    with patch("bytia_kode.agent.load_system_prompt", return_value="You are BytIA."):
        a = Agent(cfg)
    return a


def _tool_call(tc_id, name="bash", arguments='{"command": "true"}'):
    tc = MagicMock()
    tc.id = tc_id
    tc.function = {"name": name, "arguments": arguments}
    # chat() stores tc.model_dump() into Message.tool_calls (list[dict])
    tc.model_dump = lambda: {
        "id": tc_id,
        "function": {"name": name, "arguments": arguments},
    }
    return tc


async def _wait_for_subprocess(agent, task=None, timeout=10.0):
    """Espera a que la tool registre el subprocess — CON TOPE.

    Sin deadline, un wiring roto (nadie registra el proceso) colgaría el
    test para siempre en vez de fallarlo.
    """
    deadline = time.monotonic() + timeout
    while agent._active_subprocess is None:
        if task is not None and task.done():
            task.result()  # re-raise: la tool murió sin registrar nada
        if time.monotonic() > deadline:
            raise AssertionError(
                "la tool no registró ningún subprocess — kill-wiring roto"
            )
        await asyncio.sleep(0.01)


def _wire(agent, stream):
    mock_provider = AsyncMock()
    mock_provider.chat_stream = stream
    agent.providers._primary = mock_provider
    agent.providers.get = MagicMock(return_value=mock_provider)
    agent.providers.get_healthy = MagicMock(return_value=(mock_provider, "primary"))


class TestInterruptMidStream:
    """S1 — un interrupt durante la generación corta el stream y marca el turno."""

    @pytest.mark.asyncio
    async def test_interrupt_mid_stream_yields_marker_and_keeps_partial(self, agent):
        """El chunk que llega después del interrupt no se emite; el parcial sí."""
        events_seen_during_stream = []

        async def _stream(**kwargs):
            yield "text", "Hola, "
            agent._cancel_event.set()
            events_seen_during_stream.append(agent._cancel_event.is_set())
            yield "text", "ando pensando"

        _wire(agent, _stream)
        collected = []
        async for chunk in agent.chat("test"):
            collected.append(chunk)

        assert events_seen_during_stream == [True], "el stream debe ver el evento set"
        assert any("[interrupted]" in str(c) for c in collected)
        assert not any("ando pensando" in str(c) for c in collected)
        # S1+S4 (memoria): el parcial acumulado queda como turno del assistant
        assert agent.messages[-1].role == "assistant"
        assert "Hola, " in agent.messages[-1].content
        assert "ando pensando" not in agent.messages[-1].content


class TestCancelledMessagePersistedInSession:
    """S4 — el mensaje cancelado se persiste en la sesión en disco."""

    @pytest.mark.asyncio
    async def test_partial_survives_in_session_store(self, agent):
        """El parcial (no sólo agent.messages) queda en el store de la sesión."""

        async def _stream(**kwargs):
            yield "text", "Respuesta parc"
            agent._cancel_event.set()
            yield "text", "ial que no debe guardarse"

        _wire(agent, _stream)
        sid = agent._session_store.create_session("tui")
        agent._current_session_id = sid

        async for chunk in agent.chat("test"):
            pass

        rows = agent._session_store.load_messages(sid)
        assert [r["role"] for r in rows] == ["user", "assistant"]
        assert "Respuesta parc" in rows[1]["content"]
        assert "no debe guardarse" not in rows[1]["content"]

    @pytest.mark.asyncio
    async def test_reasoning_only_cancel_stores_placeholder(self, agent):
        """Cancel con sólo reasoning (sin texto) guarda el placeholder explícito."""

        async def _stream(**kwargs):
            yield "reasoning", "pensando sin texto aún..."
            agent._cancel_event.set()
            yield "text", "texto que ya no llega"

        _wire(agent, _stream)
        sid = agent._session_store.create_session("tui")
        agent._current_session_id = sid

        async for chunk in agent.chat("test"):
            pass

        rows = agent._session_store.load_messages(sid)
        assert rows[1]["role"] == "assistant"
        assert rows[1]["content"] == "(respuesta cancelada)"

    @pytest.mark.asyncio
    async def test_cancel_before_first_chunk_stores_placeholder(self, agent):
        """Cancel que aterriza antes del primer chunk: el turno queda grabado
        como cancelado (ANTES de AST-24 no dejaba nada — cambio deliberado:
        la transcripción registra que hubo respuesta cortada)."""

        async def _stream(**kwargs):
            agent._cancel_event.set()
            yield "text", "primer chunk ya con el kill puesto"

        _wire(agent, _stream)
        sid = agent._session_store.create_session("tui")
        agent._current_session_id = sid

        collected = []
        async for chunk in agent.chat("test"):
            collected.append(chunk)

        rows = agent._session_store.load_messages(sid)
        assert [r["role"] for r in rows] == ["user", "assistant"]
        assert rows[1]["content"] == "(respuesta cancelada)"
        assert not any("primer chunk" in str(c) for c in collected)


class TestKillAbortsRemainingToolBatch:
    """S2 — un kill durante una herramienta aborta el resto del lote.

    Antes de AST-24 el bucle de _handle_tool_calls no comprobaba el evento de
    cancelación entre herramientas: si el kill llegaba durante la herramienta 1
    de 3, las herramientas 2 y 3 SEGUIAN EJECUTÁNDOSE sobre un agente que el
    usuario había matado. Este es el test que falla antes del cambio.
    """

    @pytest.mark.asyncio
    async def test_kill_during_tool_skips_remaining_batch(self, agent):
        from bytia_kode.tools.registry import ToolResult

        calls = []

        async def _execute(name, args, **kw):
            calls.append(name)
            if len(calls) == 1:
                agent._cancel_event.set()  # kill() aterriza durante la 1ª tool
            return ToolResult(output="ok", error=False)

        agent.tools.execute = _execute

        call_count = 0

        async def _stream(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield "tool_calls", [_tool_call("tc_a"), _tool_call("tc_b")]
            else:
                yield "text", "respuesta-tras-kill"

        _wire(agent, _stream)
        sid = agent._session_store.create_session("tui")
        agent._current_session_id = sid

        collected = []
        async for chunk in agent.chat("test"):
            collected.append(chunk)

        assert calls == ["bash"], "la 2ª herramienta del lote no debe ejecutarse"
        assert any("[interrupted]" in str(c) for c in collected)
        assert not any("respuesta-tras-kill" in str(c) for c in collected)
        # El tool_call pendiente recibe respuesta explícita — sin colgarse
        tool_msgs = [m for m in agent.messages if m.role == "tool"]
        cancelled = [m for m in tool_msgs if m.tool_call_id == "tc_b"]
        assert cancelled, "tc_b debe quedar respondido como cancelado"
        assert "cancel" in cancelled[0].content.lower()
        # ...y en disco también
        rows = agent._session_store.load_messages(sid)
        cancelled_rows = [r for r in rows if r.get("tool_call_id") == "tc_b"]
        assert cancelled_rows and "cancel" in cancelled_rows[0]["content"].lower()


class TestKillDuringBashSubprocess:
    """S3 — kill() con un subprocess real de bash activo."""

    @pytest.mark.asyncio
    async def test_kill_terminates_registered_subprocess(self, agent):
        """El proceso vivo se registra en _active_subprocess y kill() lo termina."""
        dead = asyncio.Event()
        events = []

        class FakeProcess:
            returncode = None

            def terminate(self):
                events.append("terminate")

            async def wait(self):
                events.append("wait")
                self.returncode = -15
                dead.set()

            async def communicate(self):
                await dead.wait()
                return b"", b""

        proc = FakeProcess()

        async def _fake_spawn(*args, **kwargs):
            return proc

        with patch(
            "bytia_kode.tools.registry.asyncio.create_subprocess_exec", _fake_spawn
        ):
            task = asyncio.create_task(
                agent.tools.execute(
                    "bash", {"command": "ls"}, on_subprocess=agent._track_subprocess
                )
            )
            await _wait_for_subprocess(agent, task)
            assert agent._active_subprocess is proc
            await agent.kill()

            result = await task

        assert events[0] == "terminate"
        assert result.error is True
        assert agent._active_subprocess is None

    @pytest.mark.asyncio
    async def test_kill_escalates_to_sigkill_when_terminate_ignored(self, agent):
        """Si SIGTERM no basta en 2s, kill() escala a SIGKILL."""
        really_dead = asyncio.Event()
        events = []

        class StubbornProcess:
            returncode = None

            def terminate(self):
                events.append("terminate")

            def kill(self):
                events.append("sigkill")
                self.returncode = -9
                really_dead.set()

            async def wait(self):
                await really_dead.wait()

            async def communicate(self):
                await really_dead.wait()
                return b"", b""

        proc = StubbornProcess()

        async def _fake_spawn(*args, **kwargs):
            return proc

        with patch(
            "bytia_kode.tools.registry.asyncio.create_subprocess_exec", _fake_spawn
        ):
            task = asyncio.create_task(
                agent.tools.execute(
                    "bash", {"command": "ls"}, on_subprocess=agent._track_subprocess
                )
            )
            await _wait_for_subprocess(agent, task)
            await agent.kill()
            result = await task

        assert "terminate" in events and "sigkill" in events
        assert events.index("sigkill") > events.index("terminate")
        assert result.error is True

    @pytest.mark.asyncio
    async def test_kill_reaps_real_sleep_subprocess(self, agent, monkeypatch):
        """Subprocess REAL: sleep 30 muere por el kill(), no por el timeout."""
        from bytia_kode.tools import registry

        monkeypatch.setattr(
            registry, "_ALLOWED_BINARIES", registry._ALLOWED_BINARIES | {"sleep"}
        )
        t0 = time.monotonic()
        task = asyncio.create_task(
            agent.tools.execute(
                "bash",
                {"command": "sleep 30", "timeout": 25},
                on_subprocess=agent._track_subprocess,
            )
        )
        await _wait_for_subprocess(agent, task)
        proc = agent._active_subprocess
        await agent.kill()
        result = await task
        elapsed = time.monotonic() - t0

        assert elapsed < 10, f"el sleep sobrevivió {elapsed:.1f}s — kill inerte"
        assert result.error is True
        assert proc.returncode is not None and proc.returncode < 0
        assert agent._active_subprocess is None

    @pytest.mark.asyncio
    async def test_chat_end_to_end_kill_during_bash(self, agent, monkeypatch):
        """Integración completa: chat() → bash(sleep) → kill() → turno cortado."""
        from bytia_kode.tools import registry

        monkeypatch.setattr(
            registry, "_ALLOWED_BINARIES", registry._ALLOWED_BINARIES | {"sleep"}
        )

        call_count = 0

        async def _stream(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield "tool_calls", [
                    _tool_call(
                        "tc_sleep", arguments='{"command": "sleep 30", "timeout": 25}'
                    )
                ]
            else:
                yield "text", "no-deberia-llegar"

        _wire(agent, _stream)

        async def _killer():
            try:
                await _wait_for_subprocess(agent, timeout=15.0)
            except AssertionError:
                return  # wiring roto: sin registro no hay kill — fallarán los asserts
            await agent.kill()

        killer = asyncio.create_task(_killer())
        collected = []
        async for chunk in agent.chat("duerme"):
            collected.append(chunk)
        await killer

        assert any("[interrupted]" in str(c) for c in collected)
        assert not any("no-deberia-llegar" in str(c) for c in collected)
        assert agent._active_subprocess is None
        # H2: kill() no limpia el evento — el turno siguiente sí (H1)
        assert agent._cancel_event.is_set()


class TestCancelEventCleanNextTurn:
    """S5 — el evento queda limpio al arrancar el turno SIGUIENTE tras un kill.

    kill() no debe limpiarlo (H2: perdería el kill); chat() lo limpia una vez
    por turno (H1). El turno posterior a un kill debe streamarse completo.
    """

    @pytest.mark.asyncio
    async def test_event_cleared_at_start_of_next_turn_after_kill(self, agent):
        await agent.kill()
        assert agent._cancel_event.is_set(), "H2: kill() no limpia el evento"

        observed = []

        async def _stream(**kwargs):
            observed.append(agent._cancel_event.is_set())
            yield "text", "respuesta completa del turno nuevo"

        _wire(agent, _stream)
        collected = []
        async for chunk in agent.chat("otra pregunta"):
            collected.append(chunk)

        assert observed == [False], "H1: el turno debe arrancar con el evento limpio"
        assert not any("[interrupted]" in str(c) for c in collected)
        assert any("respuesta completa del turno nuevo" in str(c) for c in collected)
        assert "respuesta completa del turno nuevo" in agent.messages[-1].content

    @pytest.mark.asyncio
    async def test_kill_then_new_turn_streams_full_answer(self, agent):
        """Tras un kill, el proveedor del turno nuevo se consume entero."""
        call_count = 0

        async def _stream(**kwargs):
            nonlocal call_count
            call_count += 1
            yield "text", "ch1 "
            yield "text", "ch2 "
            yield "text", "ch3"

        _wire(agent, _stream)
        await agent.kill()

        collected = []
        async for chunk in agent.chat("reintento"):
            collected.append(chunk)

        text = "".join(str(c) for c in collected if isinstance(c, str))
        assert "ch1" in text and "ch3" in text
        assert "[interrupted]" not in text
