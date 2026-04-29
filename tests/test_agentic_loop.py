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
        agent.providers.get_healthy = MagicMock(return_value=(mock_provider, "primary"))

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
        agent.providers.get_healthy = MagicMock(return_value=(mock_provider, "primary"))

        collected = []
        async for chunk in agent.chat("test"):
            collected.append(chunk)

        assert len(agent.messages) == 2
        assert "<reasoning>" not in agent.messages[1].content
        assert agent.messages[1].content == "Mi respuesta."

    @pytest.mark.asyncio
    async def test_empty_text_reasoning_only_exits_loop(self, agent):
        """When model returns only reasoning (no text), loop must still exit."""
        mock_provider = AsyncMock()
        mock_provider.chat_stream = _mock_stream_response(
            text="", reasoning="Solo pensando..."
        )

        agent.providers._primary = mock_provider
        agent.providers.get = MagicMock(return_value=mock_provider)
        agent.providers.get_healthy = MagicMock(return_value=(mock_provider, "primary"))

        collected = []
        async for chunk in agent.chat("test"):
            collected.append(chunk)

        assert len(agent.messages) == 2
        assert agent.messages[1].content == "Solo pensando..."

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
        agent.providers.get_healthy = MagicMock(return_value=(mock_provider, "primary"))

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
        agent.providers.get_healthy = MagicMock(return_value=(mock_provider, "primary"))

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
        agent.providers.get_healthy = MagicMock(return_value=(mock_provider, "primary"))
        agent.providers.get_healthy = MagicMock(return_value=(mock_provider, "primary"))

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
        agent.providers.get_healthy = MagicMock(return_value=(failing_provider, "primary"))

        collected = []
        async for chunk in agent.chat("test"):
            collected.append(chunk)

        assert any("Fallback response" in str(c) for c in collected)

    @pytest.mark.asyncio
    async def test_fallback_switch_on_provider_failure(self, agent):
        """Agent retries with next provider when primary fails, no system messages needed."""
        failing_provider = AsyncMock()
        failing_provider.chat_stream = MagicMock(side_effect=ConnectionError("Down"))

        working_provider = AsyncMock()
        working_provider.chat_stream = _mock_stream_response(text="OK from fallback")

        agent.providers._primary = failing_provider
        agent.providers._fallback = working_provider
        agent.providers._circuits["primary"]._failure_threshold = 1

        agent.providers.get = MagicMock(side_effect=lambda name: {
            "primary": failing_provider,
            "fallback": working_provider,
        }[name])
        agent.providers.get_healthy = MagicMock(return_value=(failing_provider, "primary"))

        collected = []
        async for chunk in agent.chat("test"):
            collected.append(chunk)

        assert any("OK from fallback" in str(c) for c in collected)

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
        agent.providers.get_healthy = MagicMock(return_value=(failing, "primary"))

        collected = []
        async for chunk in agent.chat("test"):
            collected.append(chunk)

        error_msgs = [c for c in collected if isinstance(c, tuple) and c[0] == "error"]
        assert len(error_msgs) >= 1


class TestToolErrorMemory:
    """FIX-3: Tool Error Memory prevents re-executing rejected tool calls."""

    @pytest.mark.asyncio
    async def test_blocked_tool_call_skipped(self, agent):
        """A tool call previously rejected should be skipped with [blocked] message."""
        from bytia_kode.tools.registry import ToolResult

        tool_call = MagicMock()
        tool_call.id = "tc_001"
        tool_call.function = {"name": "bash", "arguments": '{"command": "rm -rf /"}'}

        async def _execute(name, args, **kw):
            return ToolResult(output="Security: command blocked by policy", error=True)

        agent.tools.execute = _execute

        await agent._handle_tool_calls([tool_call])

        error_msgs = [m for m in agent.messages if m.role == "tool" and "[blocked]" in m.content]
        assert len(error_msgs) == 0  # first call executes normally

        await agent._handle_tool_calls([tool_call])

        blocked_msgs = [m for m in agent.messages if m.role == "tool" and "[blocked]" in m.content]
        assert len(blocked_msgs) == 1
        assert "Previously rejected" in blocked_msgs[0].content

    @pytest.mark.asyncio
    async def test_different_command_not_blocked(self, agent):
        """A different command should not be blocked by previous error memory."""
        from bytia_kode.tools.registry import ToolResult

        async def _execute(name, args, **kw):
            return ToolResult(output="Security: blocked", error=True)

        agent.tools.execute = _execute

        tc1 = MagicMock()
        tc1.id = "tc_001"
        tc1.function = {"name": "bash", "arguments": '{"command": "rm -rf /"}'}

        tc2 = MagicMock()
        tc2.id = "tc_002"
        tc2.function = {"name": "bash", "arguments": '{"command": "ls -la"}'}

        await agent._handle_tool_calls([tc1])
        await agent._handle_tool_calls([tc2])

        blocked = [m for m in agent.messages if "[blocked]" in (m.content or "")]
        assert len(blocked) == 0  # tc2 is different, not blocked

    @pytest.mark.asyncio
    async def test_non_dangerous_tool_not_tracked(self, agent):
        """file_read and grep errors should NOT be remembered (safe to retry)."""
        from bytia_kode.tools.registry import ToolResult

        async def _execute(name, args, **kw):
            return ToolResult(output="File not found", error=True)

        agent.tools.execute = _execute

        tc = MagicMock()
        tc.id = "tc_003"
        tc.function = {"name": "file_read", "arguments": '{"path": "/no/existe"}'}

        await agent._handle_tool_calls([tc])
        await agent._handle_tool_calls([tc])

        blocked = [m for m in agent.messages if "[blocked]" in (m.content or "")]
        assert len(blocked) == 0  # file_read is not tracked


class TestWorkspaceContextInSystemPrompt:
    """FIX-4: System prompt includes workspace context for sandbox awareness."""

    def test_system_prompt_contains_cwd(self, agent, tmp_path):
        """The system prompt must contain the current working directory."""
        agent._identity_dirty = True
        sp = agent._build_system_prompt()

        assert "Workspace Context" in sp
        assert str(tmp_path) in sp

    def test_system_prompt_contains_sandbox_warning(self, agent, tmp_path):
        """The system prompt must mention sandbox constraints."""
        agent._identity_dirty = True
        sp = agent._build_system_prompt()

        assert "sandboxed" in sp
        assert "trusted paths" in sp

    def test_workspace_context_with_trusted_paths(self, agent, tmp_path):
        """Trusted paths beyond CWD should appear in the system prompt."""
        from bytia_kode.tools.registry import set_trusted_paths

        trusted = tmp_path / "external"
        trusted.mkdir()
        set_trusted_paths([trusted])

        agent._identity_dirty = True
        sp = agent._build_system_prompt()

        assert str(trusted) in sp
