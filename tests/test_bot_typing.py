"""Indicador «escribiendo…» del bot de Telegram (sendChatAction renovado).

El status de typing de la Bot API expira a los ~5 s y en modo agéntico la
respuesta puede tardar minutos: `_typing_loop` lo renueva cada tick hasta que
el caller cancela el task. Estos tests cubren el contrato: primera emisión
inmediata, cancelación limpia al terminar el chat y resiliencia ante fallos
puntuales de la API (el typing nunca tumba el chat).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("telegram", reason="python-telegram-bot not installed")

from bytia_kode.telegram.bot import TelegramBot  # noqa: E402

CHAT_ID = "424242"


def _loop_bot(interval: float = 0.01) -> TelegramBot:
    """Instancia mínima para el unit test: `__new__` salta el __init__ (que
    construye la Application de PTB) y el intervalo corto acelera los ticks."""
    bot = TelegramBot.__new__(TelegramBot)
    bot._TYPING_INTERVAL = interval
    return bot


def _fake_context() -> AsyncMock:
    context = AsyncMock()
    context.bot.send_chat_action = AsyncMock()
    return context


@pytest.mark.asyncio
async def test_primera_emision_inmediata():
    """El typing se envía en el arranque del task, no tras el primer sleep."""
    context = _fake_context()
    task = asyncio.create_task(_loop_bot()._typing_loop(context, CHAT_ID))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert context.bot.send_chat_action.await_count >= 1
    context.bot.send_chat_action.assert_awaited_with(chat_id=CHAT_ID, action="typing")


@pytest.mark.asyncio
async def test_cancelacion_limpia_sin_excepcion_colateral():
    """Cancelar el task termina en CancelledError y no deja nada colgando."""
    context = _fake_context()
    task = asyncio.create_task(_loop_bot()._typing_loop(context, CHAT_ID))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()


@pytest.mark.asyncio
async def test_fallo_puntual_no_mata_el_loop():
    """Si la API falla en un tick, el loop reintenta en el siguiente."""
    context = _fake_context()
    calls = {"n": 0}

    async def flaky(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("API caída un instante")

    context.bot.send_chat_action = AsyncMock(side_effect=flaky)
    task = asyncio.create_task(_loop_bot(interval=0.01)._typing_loop(context, CHAT_ID))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls["n"] >= 2  # el primer fallo no detuvo las renovaciones
