"""Test provider client and core runtime behaviors."""
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


def test_bash_tool_blocks_disallowed_command():
    from bytia_kode.tools.registry import BashTool

    result = asyncio.run(BashTool().execute(command="rm -rf /"))
    assert result.error
    assert "not allowed" in result.output


def test_bash_tool_runs_allowed_command_async():
    from bytia_kode.tools.registry import BashTool

    result = asyncio.run(BashTool().execute(command="echo hello"))
    assert not result.error
    assert "hello" in result.output


def test_file_tools_block_path_traversal(tmp_path, monkeypatch):
    from bytia_kode.tools.registry import FileReadTool, FileWriteTool

    monkeypatch.chdir(tmp_path)
    read_result = asyncio.run(FileReadTool().execute(path="../../etc/passwd"))
    write_result = asyncio.run(FileWriteTool().execute(path="../../escape.txt", content="no"))

    assert read_result.error
    assert write_result.error
    assert "Security violation" in read_result.output
    assert "Security violation" in write_result.output


def test_telegram_bot_fails_secure_when_allowlist_is_empty():
    from bytia_kode.config import AppConfig, ProviderConfig, TelegramConfig
    from bytia_kode.telegram.bot import TelegramBot

    config = AppConfig(
        provider=ProviderConfig(),
        telegram=TelegramConfig(bot_token="token", allowed_users=[]),
    )
    bot = TelegramBot(config)
    assert bot._is_allowed(12345) is False


def test_agent_discards_empty_or_non_printable_input():
    from bytia_kode.agent import Agent
    from bytia_kode.config import load_config

    agent = Agent(load_config())

    async def run_chat():
        return [chunk async for chunk in agent.chat("\x00\x01   \n")]

    result = asyncio.run(run_chat())
    assert result == ["Input discarded: empty or non-printable message."]
    assert agent.messages == []


def test_agent_preserves_history_on_provider_runtime_error():
    from bytia_kode.agent import Agent
    from bytia_kode.config import load_config

    class FailingProvider:
        async def chat(self, **kwargs):
            raise RuntimeError("provider exploded")

        async def chat_stream(self, **kwargs):
            raise RuntimeError("provider exploded")
            yield  # make it an async generator

    agent = Agent(load_config())
    agent.providers.get = lambda provider: FailingProvider()

    async def run_chat():
        return [chunk async for chunk in agent.chat("hola")]

    result = asyncio.run(run_chat())
    assert result == ["Provider runtime error: provider exploded"]
    assert len(agent.messages) == 1
    assert agent.messages[0].role == "user"
    assert agent.messages[0].content == "hola"




def test_telegram_bot_chat_hides_internal_errors():
    from bytia_kode.config import AppConfig, ProviderConfig, TelegramConfig
    from bytia_kode.telegram.bot import TelegramBot

    class DummyMessage:
        def __init__(self, text: str):
            self.text = text
            self.replies: list[str] = []

        async def reply_text(self, text: str):
            self.replies.append(text)

    class DummyUser:
        def __init__(self, user_id: int):
            self.id = user_id

    class DummyUpdate:
        def __init__(self):
            self.message = DummyMessage('hola')
            self.effective_user = DummyUser(1)

    class BrokenAgent:
        async def chat(self, _text: str):
            raise RuntimeError('stacktrace interno')
            yield ''

    config = AppConfig(
        provider=ProviderConfig(),
        telegram=TelegramConfig(bot_token='token', allowed_users=['1']),
    )
    bot = TelegramBot(config)
    bot._agents["1"] = BrokenAgent()
    update = DummyUpdate()

    asyncio.run(bot._chat(update, None))
    assert update.message.replies == ['Error interno en el procesamiento']

