"""Tests for SessionStore — SQLite WAL session persistence."""
from __future__ import annotations

import pytest

from bytia_kode.session import SessionStore


@pytest.fixture
def store(tmp_path):
    return SessionStore(tmp_path / "test_sessions.db")


class TestSessionLifecycle:
    def test_create_session(self, store):
        sid = store.create_session("tui")
        assert sid.startswith("tui_")
        assert len(sid) > 10

    def test_create_session_with_ref(self, store):
        sid = store.create_session("telegram", "123456")
        assert sid.startswith("telegram_")
        meta = store.get_metadata(sid)
        assert meta is not None
        assert meta.source_ref == "123456"

    def test_get_metadata_not_found(self, store):
        assert store.get_metadata("nonexistent") is None


class TestMessageOperations:
    def test_append_and_load(self, store):
        sid = store.create_session("tui")
        store.append_message(sid, "user", "Hello")
        store.append_message(sid, "assistant", "Hi there!")

        messages = store.load_messages(sid)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Hi there!"

    def test_append_updates_message_count(self, store):
        sid = store.create_session("tui")
        store.append_message(sid, "user", "msg1")
        store.append_message(sid, "user", "msg2")
        store.append_message(sid, "user", "msg3")

        meta = store.get_metadata(sid)
        assert meta.message_count == 3

    def test_append_tool_calls_json(self, store):
        sid = store.create_session("tui")
        tool_calls = [{"id": "call_1", "function": {"name": "bash", "arguments": '{"cmd":"ls"}'}}]
        store.append_message(sid, "assistant", None, tool_calls=tool_calls)

        messages = store.load_messages(sid)
        assert len(messages) == 1
        assert messages[0]["tool_calls"] == tool_calls

    def test_append_tool_result(self, store):
        sid = store.create_session("tui")
        store.append_message(sid, "tool", "output here", tool_call_id="call_1", name="bash")

        messages = store.load_messages(sid)
        assert messages[0]["tool_call_id"] == "call_1"
        assert messages[0]["name"] == "bash"

    def test_seq_num_ordering(self, store):
        sid = store.create_session("tui")
        store.append_message(sid, "user", "first")
        store.append_message(sid, "assistant", "second")
        store.append_message(sid, "user", "third")

        messages = store.load_messages(sid)
        assert messages[0]["content"] == "first"
        assert messages[1]["content"] == "second"
        assert messages[2]["content"] == "third"


class TestListAndSearch:
    def test_list_all(self, store):
        store.create_session("tui")
        store.create_session("telegram")
        sessions = store.list_sessions()
        assert len(sessions) == 2

    def test_list_by_source(self, store):
        store.create_session("tui")
        store.create_session("telegram")
        store.create_session("tui")

        tui_sessions = store.list_sessions(source="tui")
        tg_sessions = store.list_sessions(source="telegram")
        assert len(tui_sessions) == 2
        assert len(tg_sessions) == 1

    def test_search_by_title(self, store):
        sid = store.create_session("tui", title="Python refactoring help")
        store.create_session("tui", title="Bash script debugging")

        results = store.search_sessions("Python")
        assert len(results) == 1
        assert results[0].session_id == sid

    def test_list_limit(self, store):
        for _ in range(5):
            store.create_session("tui")
        sessions = store.list_sessions(limit=3)
        assert len(sessions) == 3


class TestDelete:
    def test_delete_session(self, store):
        sid = store.create_session("tui")
        store.append_message(sid, "user", "will be deleted")

        assert store.delete_session(sid) is True
        assert store.get_metadata(sid) is None
        assert store.load_messages(sid) == []

    def test_delete_nonexistent(self, store):
        assert store.delete_session("nonexistent") is False


class TestTitle:
    def test_update_title(self, store):
        sid = store.create_session("tui")
        store.update_title(sid, "My session title")
        meta = store.get_metadata(sid)
        assert meta.title == "My session title"

    def test_update_title_truncated(self, store):
        sid = store.create_session("tui")
        long_title = "A" * 200
        store.update_title(sid, long_title)
        meta = store.get_metadata(sid)
        assert len(meta.title) == 80

    def test_update_title_no_overwrite(self, store):
        sid = store.create_session("tui", title="Original")
        store.update_title(sid, "New title")
        meta = store.get_metadata(sid)
        assert meta.title == "Original"


class TestGetContext:
    def test_get_session_context(self, store):
        sid = store.create_session("tui", title="Test session")
        store.append_message(sid, "user", "What is Python?")
        store.append_message(sid, "assistant", "Python is a programming language.")

        context = store.get_session_context(sid, max_messages=5)
        assert "Test session" in context
        assert "Python" in context

    def test_get_context_not_found(self, store):
        context = store.get_session_context("nonexistent")
        assert "not found" in context.lower()


class TestPreviousSessionSummary:
    """Tests for Agent._get_previous_session_summary — context continuity."""

    @pytest.fixture
    def agent(self, tmp_path):
        from bytia_kode.agent import Agent
        from bytia_kode.config import AppConfig
        from unittest.mock import patch

        config = AppConfig(data_dir=tmp_path)
        with patch("bytia_kode.agent.ProviderManager"):
            ag = Agent.__new__(Agent)
            ag.config = config
            ag._session_store = SessionStore(tmp_path / "test.db")
            ag._current_session_id = None
            ag._system_prompt = "test"
            ag._bkode_content = ""
            return ag

    def test_no_previous_session_returns_empty(self, agent):
        result = agent._get_previous_session_summary()
        assert result == ""

    def test_summary_with_previous_session(self, agent):
        sid = agent._session_store.create_session("tui", title="Sesión de prueba")
        agent._session_store.append_message(sid, "user", "Hola, cómo estás?")
        agent._session_store.append_message(sid, "assistant", "Bien, gracias!")

        agent._current_session_id = agent._session_store.create_session("tui")
        result = agent._get_previous_session_summary()

        assert "Previous Session Context" in result
        assert "Sesión de prueba" in result
        assert sid in result

    def test_summary_excludes_current_session(self, agent):
        sid = agent._session_store.create_session("tui", title="Actual")
        agent._session_store.append_message(sid, "user", "mensaje actual")

        agent._current_session_id = sid
        result = agent._get_previous_session_summary()
        assert result == ""

    def test_summary_filters_by_source(self, agent):
        tui_sid = agent._session_store.create_session("tui", title="Sesión TUI")
        agent._session_store.append_message(tui_sid, "user", "desde TUI")
        tg_sid = agent._session_store.create_session("telegram", title="Sesión Telegram")
        agent._session_store.append_message(tg_sid, "user", "desde Telegram")

        agent._current_session_id = agent._session_store.create_session("tui")
        result = agent._get_previous_session_summary()

        assert "Sesión TUI" in result
        assert "Sesión Telegram" not in result

    def test_summary_shows_last_3_messages(self, agent):
        sid = agent._session_store.create_session("tui", title="Múltiples mensajes")
        for i in range(5):
            agent._session_store.append_message(sid, "user", f"Mensaje {i}")

        agent._current_session_id = agent._session_store.create_session("tui")
        result = agent._get_previous_session_summary()

        assert "Mensaje 2" in result
        assert "Mensaje 3" in result
        assert "Mensaje 4" in result
        assert "Mensaje 0" not in result
        assert "Mensaje 1" not in result


class TestAssistantPersistence:
    """Verify that assistant responses and reasoning are always persisted."""

    def test_user_and_assistant_both_saved(self, store):
        sid = store.create_session("tui")
        store.append_message(sid, "user", "hola")
        store.append_message(sid, "assistant", "que tal")
        msgs = store.load_messages(sid)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "hola"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"] == "que tal"

    def test_reasoning_preserved_in_assistant_content(self, store):
        sid = store.create_session("tui")
        store.append_message(sid, "user", "explica python")
        reasoning = "Debo explicar Python de forma concisa y honesta."
        response = "Python es un lenguaje de programación interpretado."
        stored = f"<reasoning>\n{reasoning}\n</reasoning>\n{response}"
        store.append_message(sid, "assistant", stored)
        msgs = store.load_messages(sid)
        assert len(msgs) == 2
        assert "<reasoning>" in msgs[1]["content"]
        assert reasoning in msgs[1]["content"]
        assert response in msgs[1]["content"]

    def test_no_reasoning_still_saves(self, store):
        sid = store.create_session("tui")
        store.append_message(sid, "user", "hola")
        store.append_message(sid, "assistant", "hola!")
        msgs = store.load_messages(sid)
        assert len(msgs) == 2
        assert "<reasoning>" not in msgs[1]["content"]
        assert msgs[1]["content"] == "hola!"

    def test_empty_response_with_reasoning_saves(self, store):
        sid = store.create_session("tui")
        store.append_message(sid, "user", "test")
        reasoning = "Pensando mucho sobre esto..."
        stored = f"<reasoning>\n{reasoning}\n</reasoning>\n[razonamiento sin respuesta de texto]"
        store.append_message(sid, "assistant", stored)
        msgs = store.load_messages(sid)
        assert reasoning in msgs[1]["content"]
        assert "[razonamiento sin respuesta de texto]" in msgs[1]["content"]

    def test_full_conversation_roundtrip(self, store):
        sid = store.create_session("tui")
        store.append_message(sid, "user", "pregunta 1")
        store.append_message(sid, "assistant", "<reasoning>\nrazonando\n</reasoning>\nrespuesta 1")
        store.append_message(sid, "user", "pregunta 2")
        store.append_message(sid, "assistant", "respuesta 2")
        store.append_message(sid, "user", "pregunta 3")
        store.append_message(sid, "assistant", "respuesta 3")
        msgs = store.load_messages(sid)
        assert len(msgs) == 6
        roles = [m["role"] for m in msgs]
        assert roles == ["user", "assistant", "user", "assistant", "user", "assistant"]
        meta = store.get_metadata(sid)
        assert meta.message_count == 6
