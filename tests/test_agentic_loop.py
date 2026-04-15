"""Tests for agentic loop termination — verifies the loop does not restart infinitely."""
import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from bytia_kode.providers.client import Message
from bytia_kode.agent import Agent


@pytest.fixture
def agent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = MagicMock()
    cfg.provider = MagicMock()
    cfg.skills_dir = Path(tmp_path / "skills")
    with patch("bytia_kode.agent.load_system_prompt", return_value="You are BytIA."):
        a = Agent(cfg)
    return a


def _mock_stream_response(text="Hola, soy BytIA.", reasoning="", tool_calls=None):
    """Build a mock chat_stream that yields text, reasoning, and tool_call chunks."""
    chunks = []
    if reasoning:
        chunks.append(("reasoning", reasoning))
    if text:
        chunks.append(("text", text))
    if tool_calls is not None:
        chunks.append(("tool_calls", tool_calls))

    async def _stream(**kwargs):
        for chunk_type, data in chunks:
            yield chunk_type, data

    return _stream


class TestAgenticLoopTermination:
    """Verify the agentic loop exits correctly after a complete response."""

    @pytest.mark.asyncio
    async def test_text_response_exits_loop(self, agent):
        """After a normal text response (no tool calls), the loop must exit immediately."""
        mock_provider = AsyncMock()
        mock_provider.chat_stream = _mock_stream_response(text="Respuesta directa.")

        agent.providers._primary = mock_provider
        agent.providers.get = MagicMock(return_value=mock_provider)

        collected = []
        async for chunk in agent.chat("hola"):
            collected.append(chunk)

        assert any("Respuesta directa." in str(c) for c in collected)
        assert len(agent.messages) == 2  # user + assistant
        assert agent.messages[0].role == "user"
        assert agent.messages[1].role == "assistant"
        assert "Respuesta directa." in agent.messages[1].content

    @pytest.mark.asyncio
    async def test_reasoning_response_exits_loop(self, agent):
        """Reasoning + text response must exit loop and store both."""
        mock_provider = AsyncMock()
        mock_provider.chat_stream = _mock_stream_response(
            reasoning="Pensando...", text="Mi respuesta."
        )

        agent.providers._primary = mock_provider
        agent.providers.get = MagicMock(return_value=mock_provider)

        collected = []
        async for chunk in agent.chat("test"):
            collected.append(chunk)

        assert len(agent.messages) == 2
        assert "<reasoning>" in agent.messages[1].content
        assert "Pensando..." in agent.messages[1].content
        assert "Mi respuesta." in agent.messages[1].content

    @pytest.mark.asyncio
    async def test_empty_text_reasoning_only_exits_loop(self, agent):
        """When model returns only reasoning (no text), loop must still exit."""
        mock_provider = AsyncMock()
        mock_provider.chat_stream = _mock_stream_response(
            text="", reasoning="Solo pensando..."
        )

        agent.providers._primary = mock_provider
        agent.providers.get = MagicMock(return_value=mock_provider)

        collected = []
        async for chunk in agent.chat("test"):
            collected.append(chunk)

        assert len(agent.messages) == 2
        assert "Solo pensando..." in agent.messages[1].content

    @pytest.mark.asyncio
    async def test_cancellation_saves_partial_and_exits(self, agent):
        """When user cancels mid-stream, partial response is saved and loop exits."""
        chunks = [
            ("text", "Hola, "),
            ("text", "estaba pens"),
        ]
        chunk_idx = 0

        async def _stream(**kwargs):
            nonlocal chunk_idx
            for ct, data in chunks:
                if chunk_idx >= 1:
                    agent._cancel_event.set()
                    yield ct, data
                    return
                yield ct, data
                chunk_idx += 1

        mock_provider = AsyncMock()
        mock_provider.chat_stream = _stream
        agent.providers._primary = mock_provider
        agent.providers.get = MagicMock(return_value=mock_provider)

        collected = []
        async for chunk in agent.chat("test"):
            collected.append(chunk)

        assert len(agent.messages) == 2
        assert agent.messages[1].role == "assistant"
        assert "Hola, " in agent.messages[1].content or "estaba pens" in agent.messages[1].content

    @pytest.mark.asyncio
    async def test_no_infinite_loop_on_normal_response(self, agent):
        """The provider must be called exactly once for a simple text response."""
        call_count = 0

        async def _stream(**kwargs):
            nonlocal call_count
            call_count += 1
            yield "text", f"Respuesta #{call_count}"

        mock_provider = AsyncMock()
        mock_provider.chat_stream = _stream
        agent.providers._primary = mock_provider
        agent.providers.get = MagicMock(return_value=mock_provider)

        collected = []
        async for chunk in agent.chat("test"):
            collected.append(chunk)

        assert call_count == 1, f"Provider was called {call_count} times — loop is not terminating!"
        assert len(agent.messages) == 2

    @pytest.mark.asyncio
    async def test_session_persistence_on_normal_response(self, agent):
        """Assistant response is persisted to session store."""
        mock_provider = AsyncMock()
        mock_provider.chat_stream = _mock_stream_response(text="Persisted!")

        agent.providers._primary = mock_provider
        agent.providers.get = MagicMock(return_value=mock_provider)

        sid = agent._session_store.create_session("tui")
        agent._current_session_id = sid

        async for chunk in agent.chat("test"):
            pass

        msgs = agent._session_store.load_messages(sid)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
        assert "Persisted!" in msgs[1]["content"]


class TestProviderFallback:
    """Verify automatic provider fallback when primary fails."""

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self, agent):
        """When primary fails, agent falls back to next available provider."""
        failing_provider = AsyncMock()
        failing_provider.chat_stream = MagicMock(side_effect=ConnectionError("Primary down"))

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
