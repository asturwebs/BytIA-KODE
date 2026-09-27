"""Tests de interrupción en la TUI (AST-24, pieza 3).

Arranque de tests de TUI con el Pilot integrado de Textual (App.run_test) —
sin dependencia nueva: pytest-textual-snapshot es sólo para snapshots SVG,
que esta issue no quiere. Por ahora se cubre el comportamiento de
interrupción (Esc / Ctrl+K / flujo _process_message); el 100% de tui.py es
deuda declarada que se come por trozos.

El agent se inyecta (BytIAKODEApp(agent=...)): un agent falso con
chat/interrupt/kill controlados permite pilotar la TUI sin providers.
"""
import asyncio
import time
from unittest.mock import MagicMock

import pytest

from bytia_kode.tui import BytIAKODEApp, ChatMessage
from textual.widgets import Static


class FakeAgent:
    """Agent de mentira: chat streameable e interrupt/kill grabados."""

    def __init__(self):
        self.config = MagicMock()
        self.interrupted = False
        self.killed = False
        self.on_tool_call = []
        self.on_tool_done = []
        self.on_subprocess = []
        self._bkode_path = None
        self.providers = None  # los workers de arranque prueban providers y se tragan el fallo

    def set_session(self, source="tui", source_ref=""):
        return "test_session"

    def interrupt(self):
        self.interrupted = True

    async def kill(self):
        self.killed = True

    async def chat(self, text, provider=None):
        yield "Par"
        for _ in range(250):  # ~5s de margen antes de rendirse
            if self.interrupted:
                yield "\n[interrupted]"
                return
            await asyncio.sleep(0.02)
        yield "cial-completa"


async def _wait_for(pilot, predicate, timeout=8.0, what="condición"):
    """Espera activa con tope: procesa la cola de mensajes mientras tanto —
    sin ello el worker del chat no avanza y el test se cuelga."""
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError(f"timeout esperando: {what}")
        await pilot.pause()
        await asyncio.sleep(0.02)


def _streaming_widget(app):
    return [
        w
        for w in app.query_one("#chat-area").children
        if getattr(w, "id", None) == "streaming-output"
    ]


def _messages(app, role):
    return [m.msg_content for m in app.query(ChatMessage) if m.role == role]


class TestInterruptBinding:
    """Esc = interrupt: llama a agent.interrupt() y avisa al usuario."""

    @pytest.mark.asyncio
    async def test_escape_interrupts_processing_agent(self):
        fake = FakeAgent()
        app = BytIAKODEApp(agent=fake)
        async with app.run_test() as pilot:
            app.is_processing = True  # hay un chat en vuelo

            await pilot.press("escape")
            await pilot.pause()

            assert fake.interrupted is True
            assert any("Interrupting" in c for c in _messages(app, "system"))

    @pytest.mark.asyncio
    async def test_escape_ignored_when_idle(self):
        fake = FakeAgent()
        app = BytIAKODEApp(agent=fake)
        async with app.run_test() as pilot:
            app.is_processing = False

            await pilot.press("escape")
            await pilot.pause()

            assert fake.interrupted is False


class TestKillBinding:
    """Ctrl+K = kill: await agent.kill(), sin streaming widget colgado."""

    @pytest.mark.asyncio
    async def test_ctrl_k_kills_and_removes_streaming_widget(self):
        fake = FakeAgent()
        app = BytIAKODEApp(agent=fake)
        async with app.run_test() as pilot:
            app.is_processing = True
            chat = app.query_one("#chat-area")
            await chat.mount(Static("parci", id="streaming-output"))
            await pilot.pause()

            await pilot.press("ctrl+k")
            await pilot.pause()

            assert fake.killed is True
            assert _streaming_widget(app) == []
            assert app.is_processing is False

    @pytest.mark.asyncio
    async def test_ctrl_k_ignored_when_idle(self):
        fake = FakeAgent()
        app = BytIAKODEApp(agent=fake)
        async with app.run_test() as pilot:
            app.is_processing = False

            await pilot.press("ctrl+k")
            await pilot.pause()

            assert fake.killed is False


class TestProcessMessageInterruption:
    """Flujo completo: submit → stream → Esc → turno cortado y finalizado."""

    @pytest.mark.asyncio
    async def test_submit_then_escape_cuts_the_turn(self):
        fake = FakeAgent()
        app = BytIAKODEApp(agent=fake)
        async with app.run_test() as pilot:
            app._submit_prompt("hola")
            await _wait_for(
                pilot,
                lambda: bool(_streaming_widget(app)),
                what="streaming widget montado",
            )
            assert app.is_processing is True

            await pilot.press("escape")
            await _wait_for(
                pilot,
                lambda: not app.is_processing,
                what="worker finalizado tras interrupt",
            )

            # El turno del assistant se montó como mensaje final...
            assistants = _messages(app, "assistant")
            assert assistants, "debe quedar mensaje de assistant tras el corte"
            assert any("Par" in c for c in assistants)
            # ...con el parcial, no con la respuesta que el interrupt cortó
            assert not any("cial-completa" in c for c in assistants)
            # ...y sin dejar el widget de streaming colgado
            assert _streaming_widget(app) == []

    @pytest.mark.asyncio
    async def test_chat_returning_quickly_finalizes_worker(self):
        """Un chat que termina rápido (ya interrumpido al primer chunk)
        finaliza el worker: mensaje de assistant montado, processing a False."""
        fake = FakeAgent()
        fake.interrupted = True  # el fake corta en la primera pasada
        app = BytIAKODEApp(agent=fake)
        async with app.run_test() as pilot:
            app._submit_prompt("hola")
            await _wait_for(
                pilot, lambda: not app.is_processing, what="worker finalizado"
            )

            assert any("Par" in c for c in _messages(app, "assistant"))
            assert _streaming_widget(app) == []
