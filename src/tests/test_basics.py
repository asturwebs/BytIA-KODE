"""Test provider client."""
import asyncio
from importlib import resources

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


def test_agent_loads_system_prompt_from_package_resource(caplog):
    from bytia_kode.agent import Agent, load_identity, load_system_prompt
    from bytia_kode.config import load_config

    with caplog.at_level("INFO"):
        payload = load_identity()

    assert payload["identity"]["version"] == "12.0.0"
    assert "Identity loaded from package resource" in caplog.text

    prompt = load_system_prompt()
    assert "BytIA Core Identity" in prompt
    assert "Pedro Luis Cuevas Villarrubia" in prompt

    resource = resources.files("bytia_kode.prompts").joinpath("core_identity.yaml")
    assert resource.is_file()

    agent = Agent(load_config())
    built_prompt = agent._build_system_prompt()
    assert "12.0.0" in built_prompt


def test_load_identity_missing_resource_raises_runtime_error(monkeypatch):
    from bytia_kode import agent as agent_module

    monkeypatch.setattr(agent_module, "CORE_IDENTITY_PACKAGE", "bytia_kode.missing_prompts")
    with pytest.raises(RuntimeError, match="Core identity resource not found"):
        agent_module.load_identity()
