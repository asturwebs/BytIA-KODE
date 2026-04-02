"""Test provider client."""
import asyncio
import pytest
from bytia_kode.providers.client import Message, ProviderClient, ToolDef


def test_message_serialization():
    msg = Message(role="user", content="Hello")
    d = msg.model_dump(exclude_none=True)
    assert d == {"role": "user", "content": "Hello"}


def test_message_with_tool_calls():
    msg = Message(
        role="assistant",
        content=None,
        tool_calls=[{"id": "call_1", "type": "function", "function": {"name": "bash", "arguments": '{"command": "ls"}'}}],
    )
    d = msg.model_dump(exclude_none=True)
    assert d["role"] == "assistant"
    assert len(d["tool_calls"]) == 1


def test_tool_result():
    from bytia_kode.tools.registry import ToolResult
    r = ToolResult(output="hello", error=False)
    assert r.output == "hello"
    assert not r.error


def test_tool_def():
    td = ToolDef(function={
        "name": "test",
        "description": "A test tool",
        "parameters": {"type": "object", "properties": {}},
    })
    d = td.model_dump()
    assert d["function"]["name"] == "test"


def test_file_write_tool_handles_relative_path(tmp_path, monkeypatch):
    from bytia_kode.tools.registry import FileWriteTool

    monkeypatch.chdir(tmp_path)
    tool = FileWriteTool()
    result = asyncio.run(tool.execute(path="out.txt", content="ok"))
    assert not result.error
    assert (tmp_path / "out.txt").read_text() == "ok"


def test_chat_stream_flag_uses_chat_stream_api():
    client = ProviderClient(base_url="https://example.com", api_key="x", model="m")
    with pytest.raises(NotImplementedError):
        asyncio.run(client.chat(messages=[Message(role="user", content="hi")], stream=True))
