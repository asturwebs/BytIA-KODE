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
