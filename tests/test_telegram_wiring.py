"""H3 (parcial) + H4: TelegramBot wiring — per-chat agents track their bash
subprocess (so /kill reaches children, like the TUI does) and resume one
deterministic session per chat_id across restarts."""
from bytia_kode.config import WorkspaceConfig
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("telegram", reason="python-telegram-bot not installed")


@pytest.fixture
def bot(tmp_path):
    from bytia_kode.telegram.bot import TelegramBot

    cfg = MagicMock()
    cfg.provider = MagicMock()
    # AST-26: el arranque del Agent lee la política de workspace del config
    cfg.workspace = WorkspaceConfig()
    # Real Paths: a MagicMock data_dir would make SessionStore materialize
    # junk dirs (see test_jeval_guardrail QA §8 note).
    cfg.data_dir = tmp_path / "data"
    cfg.skills_dir = tmp_path / "skills"
    cfg.telegram.bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    with patch("bytia_kode.agent.load_system_prompt", return_value="You are BytIA."):
        return TelegramBot(cfg)


class TestTelegramSubprocessWiring:
    """H3 (parcial): the agent must register an on_subprocess callback
    (tui.py parity) so /kill can terminate the bash subprocess."""

    def test_agent_tracks_active_subprocess(self, bot):
        agent = bot._get_agent("42")
        assert agent.on_subprocess, "TelegramBot must wire on_subprocess"

        sentinel = object()
        for cb in agent.on_subprocess:
            cb(sentinel)
        assert agent._active_subprocess is sentinel

        for cb in agent.on_subprocess:
            cb(None)
        assert agent._active_subprocess is None


class TestTelegramSessionResume:
    """H4: one deterministic session per chat_id, resumable across restarts."""

    def test_session_id_is_deterministic(self, bot):
        agent = bot._get_agent("123")
        assert agent._current_session_id == "telegram_123"

    def test_session_resumes_after_restart(self, bot):
        a1 = bot._get_agent("123")
        bot.session_store.append_message(a1._current_session_id, role="user", content="hola")

        bot._agents.clear()  # simulate a bot restart
        a2 = bot._get_agent("123")

        assert a2._current_session_id == "telegram_123"
        assert len(a2.messages) == 1
        assert a2.messages[0].content == "hola"

    def test_sessions_are_isolated_per_chat(self, bot):
        assert bot._get_agent("111")._current_session_id == "telegram_111"
        assert bot._get_agent("222")._current_session_id == "telegram_222"
