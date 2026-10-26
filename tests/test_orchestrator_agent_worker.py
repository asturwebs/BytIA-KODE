"""Contrato del jail del worker y del worker agéntico (F2/T8).

R5: el jail del registry es estado global; alrededor de cada worker se hace
save/restore explícito (workers secuenciales ⇒ race-free) y el worker queda
confinado a `scratch/` con trusted ∅. El worker es una instancia `Agent`
completa, con techo de iteraciones y tokens estimados en el presupuesto.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bytia_kode.orchestrator.agent_worker import AgentWorker
from bytia_kode.orchestrator.jail import worker_jail
from bytia_kode.tools import registry


@pytest.fixture(autouse=True)
def restore_jail():
    state = registry.snapshot_workspace_policy()
    yield
    registry.restore_workspace_policy(state)


def set_outside_jail(tmp_path: Path) -> Path:
    outside = tmp_path / "outside"
    outside.mkdir()
    registry.set_workspace_mode("permissive")
    registry.set_workspace_root(outside)
    registry.replace_trusted_paths([outside])
    return outside


class FakeAgent:
    instances: list["FakeAgent"] = []

    def __init__(self, config):
        self.config = config
        self.max_iterations = 50
        self.providers = self
        self.pinned = None
        self.closed = False
        self.seen_jail = None
        FakeAgent.instances.append(self)

    def pin(self, name):
        self.pinned = name

    async def chat(self, prompt, provider="primary"):
        self.seen_jail = registry.snapshot_workspace_policy()
        yield "### NOTES\nhecho\n"
        yield ("reasoning", "pensando")
        yield "### NEXT\nnada\n### STATUS\nsolved\n"

    async def close(self):
        self.closed = True

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return len(text) // 4


class TestWorkerJail:
    def test_confines_worker_and_restores(self, tmp_path):
        outside = set_outside_jail(tmp_path)
        scratch = tmp_path / "scratch"
        scratch.mkdir()

        with worker_jail(scratch):
            state = registry.snapshot_workspace_policy()
            assert state["mode"] == "confined"
            assert state["workspace"] == scratch.resolve()
            assert state["trusted"] == []

        state = registry.snapshot_workspace_policy()
        assert state["mode"] == "permissive"
        assert state["workspace"] == outside.resolve()
        assert state["trusted"] == [outside.resolve()]

    def test_restores_on_error(self, tmp_path):
        set_outside_jail(tmp_path)
        scratch = tmp_path / "scratch"
        scratch.mkdir()

        with pytest.raises(RuntimeError):
            with worker_jail(scratch):
                raise RuntimeError("boom")

        assert registry.get_workspace_mode() == "permissive"


class FakeErrorAgent(FakeAgent):
    async def chat(self, prompt, provider="primary"):
        yield ("error", "network down")


class TestAgentWorker:
    def test_runs_agent_with_cap_and_provider(self, tmp_path):
        set_outside_jail(tmp_path)
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        worker = AgentWorker(
            config=object(),
            scratch=scratch,
            provider="local",
            max_iter=12,
            agent_factory=FakeAgent,
        )

        reply = worker("worker", "hazlo")

        agent = FakeAgent.instances[-1]
        assert agent.max_iterations == 12
        assert agent.pinned == "local"
        assert agent.closed is True
        assert "### NOTES" in reply.text
        assert "### STATUS" in reply.text
        assert "pensando" not in reply.text
        assert agent.seen_jail["mode"] == "confined"
        assert agent.seen_jail["workspace"] == scratch.resolve()
        assert reply.tokens > 0

    def test_error_chunk_raises_for_infra(self, tmp_path):
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        worker = AgentWorker(
            config=object(),
            scratch=scratch,
            agent_factory=FakeErrorAgent,
        )

        with pytest.raises(RuntimeError):
            worker("worker", "hazlo")

    def test_jail_is_restored_after_worker(self, tmp_path):
        outside = set_outside_jail(tmp_path)
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        worker = AgentWorker(
            config=object(),
            scratch=scratch,
            provider="local",
            agent_factory=FakeAgent,
        )

        worker("worker", "hazlo")

        state = registry.snapshot_workspace_policy()
        assert state["mode"] == "permissive"
        assert state["trusted"] == [outside.resolve()]
