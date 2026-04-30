"""Tests for Agent context management — summarization and token estimation."""
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
    with patch("bytia_kode.agent.load_system_prompt", return_value="You are a helpful assistant."):
        a = Agent(cfg)
    return a


@pytest.fixture
def mock_provider():
    p = AsyncMock()
    p.chat = AsyncMock(return_value=Message(role="assistant", content="Resumen: el usuario preguntó sobre Python y se discutió POO."))
    return p


class TestEstimateTokens:
    def test_static_method_basic(self):
        assert Agent.estimate_tokens("hello world") == len("hello world") // 3

    def test_static_method_empty(self):
        assert Agent.estimate_tokens("") == 0

    def test_static_method_unicode(self):
        text = "Hola mundo, qué tal estás"
        result = Agent.estimate_tokens(text)
        assert 0 < result <= len(text)


class TestManageContext:
    @pytest.mark.asyncio
    async def test_no_action_when_under_threshold(self, agent, mock_provider):
        agent._max_context_tokens = 100000
        agent.messages = [
            Message(role="user", content="hi"),
            Message(role="assistant", content="hello"),
        ]
        await agent._manage_context(mock_provider)
        assert len(agent.messages) == 2
        mock_provider.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarizes_when_over_threshold(self, agent, mock_provider):
        agent._max_context_tokens = 30
        long_msg = "x" * 200
        agent.messages = [
            Message(role="user", content=long_msg),
            Message(role="assistant", content=long_msg),
            Message(role="user", content=long_msg),
            Message(role="assistant", content=long_msg),
            Message(role="user", content="keep"),
            Message(role="assistant", content="keep"),
        ]
        await agent._manage_context(mock_provider)
        assert len(agent.messages) < 6
        assert any("Conversación resumida" in (m.content or "") for m in agent.messages)

    @pytest.mark.asyncio
    async def test_preserves_recent_messages(self, agent, mock_provider):
        agent._max_context_tokens = 30
        long_msg = "x" * 200
        agent.messages = [
            Message(role="user", content=long_msg),
            Message(role="assistant", content=long_msg),
            Message(role="user", content=long_msg),
            Message(role="assistant", content=long_msg),
            Message(role="user", content="latest question"),
            Message(role="assistant", content="latest answer"),
        ]
        await agent._manage_context(mock_provider)
        assert agent.messages[-1].content == "latest answer"
        assert agent.messages[-2].content == "latest question"

    @pytest.mark.asyncio
    async def test_stops_when_few_messages_remain(self, agent, mock_provider):
        agent._max_context_tokens = 10
        agent.messages = [
            Message(role="user", content="a"),
            Message(role="assistant", content="b"),
            Message(role="user", content="c"),
            Message(role="assistant", content="d"),
            Message(role="user", content="e"),
        ]
        await agent._manage_context(mock_provider)
        assert len(agent.messages) >= 4


class TestSummarizeMessages:
    @pytest.mark.asyncio
    async def test_returns_model_summary(self, agent, mock_provider):
        msgs = [
            Message(role="user", content="Explícame POO en Python"),
            Message(role="assistant", content="POO es un paradigma que usa clases y objetos..."),
        ]
        result = await agent._summarize_messages(msgs, mock_provider)
        assert "Resumen" in result
        mock_provider.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_on_provider_error(self, agent):
        failing_provider = AsyncMock()
        failing_provider.chat.side_effect = RuntimeError("connection refused")

        msgs = [
            Message(role="user", content="Pregunta sobre Python"),
            Message(role="assistant", content="Respuesta larga sobre Python con muchos detalles"),
        ]
        result = await agent._summarize_messages(msgs, failing_provider)
        assert "USE" in result or "ASS" in result

    @pytest.mark.asyncio
    async def test_fallback_on_empty_response(self, agent):
        empty_provider = AsyncMock()
        empty_provider.chat.return_value = Message(role="assistant", content="")

        msgs = [
            Message(role="user", content="Hola"),
            Message(role="assistant", content="Qué tal"),
        ]
        result = await agent._summarize_messages(msgs, empty_provider)
        assert "USE" in result or "ASS" in result


class TestUpdateContextLimit:
    def test_updates_max_context(self, agent):
        agent.update_context_limit(32768)
        assert agent._max_context_tokens == 32768

    def test_ignores_zero(self, agent):
        original = agent._max_context_tokens
        agent.update_context_limit(0)
        assert agent._max_context_tokens == original

    def test_ignores_negative(self, agent):
        original = agent._max_context_tokens
        agent.update_context_limit(-1)
        assert agent._max_context_tokens == original


class TestSystemMessagePreservation:
    @pytest.mark.asyncio
    async def test_system_messages_survive_compression(self, agent, mock_provider):
        agent._max_context_tokens = 30
        long_msg = "x" * 200
        system_content = "CRITICAL_INSTRUCTION: never delete this"

        agent.messages = [
            Message(role="system", content="You are BytIA."),
            Message(role="user", content=long_msg),
            Message(role="assistant", content=long_msg),
            Message(role="system", content=system_content),
            Message(role="user", content=long_msg),
            Message(role="assistant", content=long_msg),
            Message(role="user", content="latest question"),
            Message(role="assistant", content="latest answer"),
        ]

        await agent._manage_context(mock_provider)

        all_content = [m.content for m in agent.messages]
        assert "You are BytIA." in all_content
        assert "CRITICAL_INSTRUCTION: never delete this" in all_content
        assert agent.messages[-1].content == "latest answer"
        assert agent.messages[-2].content == "latest question"
        assert len(agent.messages) < 8
