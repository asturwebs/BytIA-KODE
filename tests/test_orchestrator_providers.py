"""Contrato de los providers del orquestador (F2/T9).

El runner habla con un único `provider(role, prompt)`. `RoleProvider` rutea:
worker → AgentWorker (agéntico), resto → TextProvider (manager). Un fallo
del provider (circuit abierto, timeout) llega al runner como excepción y se
convierte en estado `infra`.
"""

from __future__ import annotations

import pytest

from bytia_kode.orchestrator.ledger import Ledger
from bytia_kode.orchestrator.providers import RoleProvider, TextProvider
from bytia_kode.orchestrator.runner import Reply, Runner, RunnerConfig, Verdict
from bytia_kode.orchestrator.specs import CODE_REPO
from bytia_kode.providers.client import ProviderResponse


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.closed = False

    async def chat(self, messages, **kwargs):
        if self.error:
            raise self.error
        return self.response

    async def close(self):
        self.closed = True


class TestTextProvider:
    def test_uses_real_usage(self):
        client = FakeClient(
            ProviderResponse(content="hola", usage={"total_tokens": 42})
        )
        provider = TextProvider(client_factory=lambda: client)

        reply = provider("primary_plan", "prompt")

        assert reply.text == "hola"
        assert reply.tokens == 42
        assert client.closed is True

    def test_estimates_without_usage(self):
        provider = TextProvider(
            client_factory=lambda: FakeClient(ProviderResponse(content="hola"))
        )

        reply = provider("primary_plan", "prompt")

        assert reply.tokens > 0


class TestRoleProvider:
    def test_routes_worker_and_manager(self):
        calls = []

        def worker(role, prompt):
            calls.append(("worker", role))
            return Reply("w", 1)

        def text(role, prompt):
            calls.append(("text", role))
            return Reply("t", 1)

        router = RoleProvider(worker=worker, text=text)

        assert router("worker", "p").text == "w"
        assert router("primary_plan", "p").text == "t"
        assert calls == [("worker", "worker"), ("text", "primary_plan")]


class TestCircuitFailure:
    def test_provider_failure_returns_infra(self, tmp_path):
        def text(role, prompt):
            raise RuntimeError("circuit open: local")

        def worker(role, prompt):
            return Reply("### NOTES\na\n### NEXT\nb\n### STATUS\nsolved\n", 1)

        router = RoleProvider(worker=worker, text=text)
        runner = Runner(
            ledger=Ledger(tmp_path / "ws"),
            spec=CODE_REPO,
            provider=router,
            verifier=lambda: Verdict(ok=True),
            config=RunnerConfig(),
        )

        result = runner.run("problema")

        assert result.status == "infra"
        assert "circuit open" in result.detail
