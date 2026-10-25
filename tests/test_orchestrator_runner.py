"""Contrato del runner del orquestador (F1, T4a: bucle + presupuestos).

El runner es síncrono en F1 (el bucle real de KODE es async; la adaptación
es F2). El provider y el verifier se inyectan: los tests no tocan GPU ni
git. Cada llamada deja una entrada en record.jsonl.
"""

from __future__ import annotations

from bytia_kode.orchestrator.ledger import Ledger
from bytia_kode.orchestrator.runner import (
    Reply,
    Runner,
    RunnerConfig,
    Verdict,
)
from bytia_kode.orchestrator.specs import CODE_REPO


class FakeProvider:
    """Devuelve respuestas en orden y registra los roles invocados."""

    def __init__(self, texts: list[str], tokens_per_reply: int = 10):
        self.texts = list(texts)
        self.tokens_per_reply = tokens_per_reply
        self.roles: list[str] = []

    def __call__(self, role: str, prompt: str) -> Reply:
        self.roles.append(role)
        if not self.texts:
            raise AssertionError(f"respuesta inesperada para rol {role}")
        return Reply(text=self.texts.pop(0), tokens=self.tokens_per_reply)


PLAN = "### PLAN\nResolver el problema\n### TASKS\n- implementar\n"
IDEATION = "### NOTES\nEnfoque directo\n### NEXT\nimplementar\n"
WORKER = "### NOTES\nImplementado\n### NEXT\nverificar\n### STATUS\nsolved\n"
MANAGE_DONE = "### STATUS\ndone\n### TASKS\n- implementar (done)\n"
MANAGE_CONTINUE = "### STATUS\ncontinue\n### NEXT\nseguir\n### TASKS\n- implementar\n"


def make_runner(tmp_path, texts, *, config=None, verifier=None, clock=None, tokens_per_reply=10):
    ledger = Ledger(tmp_path / "ws")
    provider = FakeProvider(texts, tokens_per_reply=tokens_per_reply)
    runner = Runner(
        ledger=ledger,
        spec=CODE_REPO,
        provider=provider,
        verifier=verifier or (lambda: Verdict(ok=True)),
        config=config or RunnerConfig(),
        clock=clock or (lambda: 0.0),
    )
    return runner, ledger, provider


class TestHappyPath:
    def test_reaches_done_in_one_round(self, tmp_path):
        runner, _, _ = make_runner(tmp_path, [PLAN, IDEATION, WORKER, MANAGE_DONE])

        result = runner.run("problema")

        assert result.status == "done"
        assert result.rounds == 1

    def test_writes_plan_and_notes_to_ledger(self, tmp_path):
        runner, ledger, _ = make_runner(tmp_path, [PLAN, IDEATION, WORKER, MANAGE_DONE])

        runner.run("problema")

        assert "Resolver el problema" in ledger.read_text("plan.md")
        assert "Implementado" in ledger.read_text("notes.md")

    def test_records_every_call_with_role(self, tmp_path):
        runner, ledger, provider = make_runner(
            tmp_path, [PLAN, IDEATION, WORKER, MANAGE_DONE]
        )

        runner.run("problema")

        entries = ledger.record_entries()
        assert [e["role"] for e in entries] == provider.roles
        assert len(entries) == 4


class TestBudgets:
    def test_round_budget_stops_when_never_done(self, tmp_path):
        runner, _, _ = make_runner(
            tmp_path,
            [PLAN, IDEATION, WORKER, MANAGE_CONTINUE, WORKER, MANAGE_CONTINUE],
            config=RunnerConfig(max_rounds=2),
        )

        result = runner.run("problema")

        assert result.status == "budget"
        assert result.rounds == 2

    def test_token_budget_stops_early(self, tmp_path):
        runner, _, _ = make_runner(
            tmp_path,
            [PLAN, IDEATION, WORKER, MANAGE_DONE],
            config=RunnerConfig(max_tokens=15),
            tokens_per_reply=10,
        )

        result = runner.run("problema")

        assert result.status == "budget"
        assert result.tokens >= 15

    def test_wallclock_budget_stops_early(self, tmp_path):
        ticks = iter([0.0, 999.0, 999.0, 999.0, 999.0, 999.0, 999.0])

        runner, _, _ = make_runner(
            tmp_path,
            [PLAN, IDEATION, WORKER, MANAGE_CONTINUE, WORKER, MANAGE_CONTINUE],
            config=RunnerConfig(max_wallclock_s=10.0),
            clock=lambda: next(ticks, 999.0),
        )

        result = runner.run("problema")

        assert result.status == "budget"
        assert result.rounds == 1
