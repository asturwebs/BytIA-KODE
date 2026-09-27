"""Tests for the JEVAL guardrail (Jev pre-execution classifier)."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bytia_kode import guardrail
from bytia_kode.agent import Agent
from bytia_kode.tools.registry import ToolResult


@pytest.fixture(autouse=True)
def _reset_gate():
    guardrail._gate = None
    yield
    guardrail._gate = None


def _gate(mode, monkeypatch):
    monkeypatch.setenv("JEVAL_MODE", mode)
    # Hermetic: the suite must pass without TYPESAFE_API_KEY in the environment.
    monkeypatch.setattr(guardrail, "_load_key", lambda: "test-key")
    return guardrail.JevalGate()


def _jev_answer(noul):
    return {"answers": {"is_risky": {"type": "noul", "noul": noul}}}


def _tool_call(name="bash", args='{"command": "echo hi"}'):
    tc = MagicMock()
    tc.function = {"name": name, "arguments": args}
    tc.id = "call_1"
    return tc


class TestJevalModes:
    def test_off_by_default(self, monkeypatch):
        monkeypatch.delenv("JEVAL_MODE", raising=False)
        g = guardrail.JevalGate()
        assert g.enabled is False

    @pytest.mark.asyncio
    async def test_off_is_noop(self, monkeypatch):
        monkeypatch.delenv("JEVAL_MODE", raising=False)
        g = guardrail.JevalGate()
        res = await g.check("bash", {"command": "ls"})
        assert res["blocked"] is False and res["mode"] == "off"

    @pytest.mark.asyncio
    async def test_shadow_never_blocks_and_is_fire_and_forget(self, monkeypatch):
        g = _gate("shadow", monkeypatch)
        with patch.object(g, "_ask_sync", return_value=_jev_answer(0.95)) as m:
            res = await g.check("bash", {"command": "rm -rf /tmp/x"})
            assert res["blocked"] is False
            assert "noul" not in res  # verdicto llega en background
            assert res["task"] is not None
            await res["task"]          # drena la tarea para el log
            m.assert_called_once()

    @pytest.mark.asyncio
    async def test_enforce_blocks_risky(self, monkeypatch):
        g = _gate("enforce", monkeypatch)
        with patch.object(g, "_ask_sync", return_value=_jev_answer(0.95)):
            res = await g.check("bash", {"command": "mkfs.ext4 /dev/sda"})
        assert res["blocked"] is True

    @pytest.mark.asyncio
    async def test_enforce_allows_safe(self, monkeypatch):
        g = _gate("enforce", monkeypatch)
        with patch.object(g, "_ask_sync", return_value=_jev_answer(0.1)):
            res = await g.check("grep", {"pattern": "foo"})
        assert res["blocked"] is False

    @pytest.mark.asyncio
    async def test_fail_open_on_error(self, monkeypatch):
        g = _gate("enforce", monkeypatch)

        def boom(state):
            raise TimeoutError("jev down")

        with patch.object(g, "_ask_sync", side_effect=boom):
            res = await g.check("bash", {"command": "ls"})
        assert res["blocked"] is False
        assert "fail-open" in res["reason"]

    def test_no_key_disables(self, monkeypatch):
        monkeypatch.setenv("JEVAL_MODE", "enforce")
        monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
        monkeypatch.setattr(guardrail, "_load_key", lambda: None)
        assert guardrail.JevalGate().enabled is False


class TestFailOpenOnMalformedResponse:
    """M1: parsing the Jev response must live inside the fail-open try — a
    non-dict body or `noul: null` used to raise past it and break the turn,
    violating the "Never raises" contract of _classify."""

    @pytest.mark.asyncio
    async def test_non_dict_body_fail_open(self, monkeypatch):
        g = _gate("enforce", monkeypatch)
        with patch.object(g, "_ask_sync", return_value=["not", "a", "dict"]):
            v = await g._classify("bash", "state", "rec_m1a")
        assert v["blocked"] is False
        assert "fail-open" in v["reason"]

    @pytest.mark.asyncio
    async def test_noul_null_fail_open(self, monkeypatch):
        g = _gate("enforce", monkeypatch)
        with patch.object(g, "_ask_sync", return_value={"answers": {"is_risky": {"noul": None}}}):
            v = await g._classify("bash", "state", "rec_m1b")
        assert v["blocked"] is False
        assert "fail-open" in v["reason"]

    @pytest.mark.asyncio
    async def test_enforce_check_never_raises_on_malformed(self, monkeypatch):
        g = _gate("enforce", monkeypatch)
        with patch.object(g, "_ask_sync", return_value=None):
            res = await g.check("bash", {"command": "ls"})
        assert res["blocked"] is False
        assert "fail-open" in res["reason"]


class TestShadowTaskKeepalive:
    """M2: shadow tasks are held by a module-level strong-ref set — without
    it the GC can cancel a task before its JSONL verdict lands."""

    @pytest.mark.asyncio
    async def test_shadow_task_completes_logs_and_is_released(self, monkeypatch, tmp_path):
        g = _gate("shadow", monkeypatch)
        monkeypatch.setattr(guardrail, "STATE_DIR", tmp_path / "state")
        # NB: drain the task INSIDE the patch — outside it the task would
        # bypass the mock and hit the real API (breaking hermeticity).
        with patch.object(g, "_ask_sync", return_value=_jev_answer(0.9)):
            res = await g.check("bash", {"command": "ls"})
            task = res["task"]
            assert task in guardrail._shadow_tasks  # strong ref while running

            await asyncio.wait_for(task, timeout=5)
        assert task.done() and not task.cancelled()

        log = tmp_path / "state" / "kode-guardrail.jsonl"
        assert log.exists()
        rec = json.loads(log.read_text().strip().splitlines()[-1])
        assert rec["tool"] == "bash"
        assert rec["noul"] == 0.9
        assert task not in guardrail._shadow_tasks  # released when done


class TestAgentIntegration:
    def _agent(self, tmp_path):
        cfg = MagicMock()
        cfg.provider = MagicMock()
        # Real Path: a MagicMock data_dir makes SessionStore materialize
        # `MagicMock/...` dirs and a real SQLite db in the repo tree (QA §8).
        cfg.data_dir = tmp_path / "data"
        cfg.skills_dir = tmp_path / "skills"
        with patch("bytia_kode.agent.load_system_prompt", return_value="You are BytIA."):
            return Agent(cfg)

    @pytest.mark.asyncio
    async def test_shadow_mode_tool_still_executes(self, monkeypatch, tmp_path):
        agent = self._agent(tmp_path)
        g = _gate("shadow", monkeypatch)
        monkeypatch.setattr(guardrail, "_gate", g)
        agent.tools.execute = AsyncMock(return_value=ToolResult(output="hi"))
        with patch.object(g, "_ask_sync", return_value=_jev_answer(0.99)):
            await agent._handle_tool_calls([_tool_call()])
            await asyncio.sleep(0.05)  # drena la tarea background del shadow
        assert agent.tools.execute.await_count == 1
        assert not any(
            m.role == "tool" and str(m.content).startswith("[blocked]")
            for m in agent.messages
        )

    @pytest.mark.asyncio
    async def test_enforce_mode_blocks_risky_tool(self, monkeypatch, tmp_path):
        agent = self._agent(tmp_path)
        g = _gate("enforce", monkeypatch)
        monkeypatch.setattr(guardrail, "_gate", g)
        agent.tools.execute = AsyncMock(return_value=ToolResult(output="hi"))
        with patch.object(g, "_ask_sync", return_value=_jev_answer(0.99)):
            await agent._handle_tool_calls([_tool_call("bash", '{"command": "dd if=/dev/zero of=/dev/sda"}')])
        assert agent.tools.execute.await_count == 0
        assert any(
            m.role == "tool" and "[blocked] JEVAL" in str(m.content)
            for m in agent.messages
        )

    @pytest.mark.asyncio
    async def test_off_mode_no_network(self, monkeypatch, tmp_path):
        agent = self._agent(tmp_path)
        monkeypatch.delenv("JEVAL_MODE", raising=False)
        agent.tools.execute = AsyncMock(return_value=ToolResult(output="hi"))
        with patch.object(guardrail.JevalGate, "check", side_effect=AssertionError("must not run")):
            await agent._handle_tool_calls([_tool_call()])
        assert agent.tools.execute.await_count == 1
