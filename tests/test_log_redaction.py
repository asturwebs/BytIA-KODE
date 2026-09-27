"""T8 (AST-16 O1-C): tool-call arguments must never reach the logs in clear text."""
import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import bytia_kode.guardrail as guardrail
from bytia_kode.agent import Agent


@pytest.fixture
def agent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # JEVAL must never swallow the tool call before it reaches the logger.
    monkeypatch.setenv("JEVAL_MODE", "off")
    monkeypatch.setattr(guardrail, "_gate", None)
    cfg = MagicMock()
    cfg.provider = MagicMock()
    cfg.data_dir = tmp_path / "data"
    cfg.skills_dir = Path(tmp_path / "skills")
    with patch("bytia_kode.agent.load_system_prompt", return_value="You are BytIA."):
        a = Agent(cfg)
    return a


def _tool_call(tool_name: str, arguments) -> MagicMock:
    tc = MagicMock()
    tc.id = "tc_redact"
    tc.function = {"name": tool_name, "arguments": arguments}
    return tc


class TestToolCallLogRedaction:
    """The log line must carry keys + hash, never the raw argument values."""

    @pytest.mark.asyncio
    async def test_long_secret_argument_not_logged(self, agent, caplog):
        from bytia_kode.tools.registry import ToolResult

        secret = "sk-" + "RedactMe" * 40  # >300 chars, looks like a credential

        async def _execute(name, args, **kw):
            return ToolResult(output="written")

        agent.tools.execute = _execute
        tc = _tool_call(
            "file_write",
            json.dumps({"path": "/tmp/notes.md", "content": secret}),
        )

        with caplog.at_level(logging.INFO, logger="bytia_kode.agent"):
            await agent._handle_tool_calls([tc])

        logged = "\n".join(record.getMessage() for record in caplog.records)
        assert "file_write" in logged
        # keys survive...
        assert "content=" in logged
        assert "path=" in logged
        # ...but no complete value does (T8: ni un valor de argumento completo)
        assert secret not in logged
        assert "RedactMe" not in logged
        assert "sha256:" in logged
        assert "notes.md" not in logged

    @pytest.mark.asyncio
    async def test_malformed_json_arguments_not_logged(self, agent, caplog):
        secret = "sk-" + "RedactMe" * 40
        # invalid JSON on purpose: hits the decode-error branch before execution
        tc = _tool_call("bash", '{"command": "' + secret)

        with caplog.at_level(logging.ERROR, logger="bytia_kode.agent"):
            await agent._handle_tool_calls([tc])

        logged = "\n".join(record.getMessage() for record in caplog.records)
        assert "Failed to decode JSON arguments" in logged
        assert secret not in logged
        assert "RedactMe" not in logged
        assert "sha256:" in logged
