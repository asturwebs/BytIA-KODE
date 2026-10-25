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
    """Devuelve respuestas en orden y registra roles y prompts."""

    def __init__(self, texts: list[str], reply_tokens: int = 10):
        self.texts = list(texts)
        self.reply_tokens = reply_tokens
        self.roles: list[str] = []
        self.prompts: list[str] = []

    def __call__(self, role: str, prompt: str) -> Reply:
        self.roles.append(role)
        self.prompts.append(prompt)
        if not self.texts:
            raise AssertionError(f"respuesta inesperada para rol {role}")
        return Reply(text=self.texts.pop(0), tokens=self.reply_tokens)


PLAN = "### PLAN\nResolver el problema\n### TASKS\n- implementar\n"
IDEATION = "### NOTES\nEnfoque directo\n### NEXT\nimplementar\n"
WORKER = "### NOTES\nImplementado\n### NEXT\nverificar\n### STATUS\nsolved\n"
MANAGE_DONE = "### STATUS\ndone\n### TASKS\n- implementar (done)\n"
MANAGE_CONTINUE = "### STATUS\ncontinue\n### NEXT\nseguir\n### TASKS\n- implementar\n"
MANAGE_CONTINUE_NO_NEXT = "### STATUS\ncontinue\n### TASKS\n- seguir\n"


def make_runner(
    tmp_path,
    texts,
    *,
    config=None,
    verifier=None,
    clock=None,
    reply_tokens=10,
    tamper_check=None,
    restore_tests=None,
    preflight=None,
    base_sha=None,
):
    ledger = Ledger(tmp_path / "ws")
    provider = FakeProvider(texts, reply_tokens=reply_tokens)
    runner = Runner(
        ledger=ledger,
        spec=CODE_REPO,
        provider=provider,
        verifier=verifier or (lambda: Verdict(ok=True)),
        config=config or RunnerConfig(),
        clock=clock or (lambda: 0.0),
        tamper_check=tamper_check,
        restore_tests=restore_tests,
        preflight=preflight,
        base_sha=base_sha,
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
        assert [e["role"] for e in entries if e["role"] != "result"] == provider.roles


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
            reply_tokens=10,
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
        assert result.rounds == 0


class TestTamperAndInvariants:
    def test_two_consecutive_tampered_rounds_abort(self, tmp_path):
        tamper = iter([True, True])

        runner, _, provider = make_runner(
            tmp_path,
            [PLAN, IDEATION, WORKER, WORKER],
            config=RunnerConfig(max_rounds=4),
            tamper_check=lambda: next(tamper, False),
        )

        result = runner.run("problema")

        assert result.status == "protocol"
        assert "test-tamper" in result.detail
        assert result.rounds == 2
        assert provider.roles == ["primary_plan", "ideation", "worker", "worker"]

    def test_tampered_round_counts_against_max_rounds(self, tmp_path):
        tamper = iter([True, False])

        runner, _, provider = make_runner(
            tmp_path,
            [PLAN, IDEATION, WORKER, WORKER, MANAGE_CONTINUE],
            config=RunnerConfig(max_rounds=2),
            tamper_check=lambda: next(tamper, False),
        )

        result = runner.run("problema")

        assert result.status == "budget"
        assert result.rounds == 2
        assert provider.roles.count("worker") == 2

    def test_done_with_failed_verdict_is_not_accepted(self, tmp_path):
        runner, _, _ = make_runner(
            tmp_path,
            [PLAN, IDEATION, WORKER, MANAGE_DONE],
            config=RunnerConfig(max_rounds=1),
            verifier=lambda: Verdict(ok=False, detail="tests rojos"),
        )

        result = runner.run("problema")

        assert result.status == "budget"

    def test_continue_without_next_uses_first_pending_task(self, tmp_path):
        runner, _, provider = make_runner(
            tmp_path,
            [PLAN, IDEATION, WORKER, MANAGE_CONTINUE_NO_NEXT, WORKER, MANAGE_DONE],
            config=RunnerConfig(max_rounds=2),
        )

        result = runner.run("problema")

        assert result.status == "done"
        assert "seguir" in provider.prompts[4]

    def test_worker_protocol_error_stops(self, tmp_path):
        runner, _, _ = make_runner(
            tmp_path,
            [PLAN, IDEATION, "texto sin secciones"],
            config=RunnerConfig(protocol_retries=0),
        )

        result = runner.run("problema")

        assert result.status == "protocol"
        assert "missing: NOTES" in result.detail


class TestReviewFixes:
    def test_status_with_trailing_text_is_done(self, tmp_path):
        manage = "### STATUS\ndone — suite verde\n### TASKS\n- implementar (done)\n"
        runner, _, _ = make_runner(tmp_path, [PLAN, IDEATION, WORKER, manage])

        result = runner.run("problema")

        assert result.status == "done"

    def test_budget_checked_before_every_call(self, tmp_path):
        runner, _, _ = make_runner(
            tmp_path,
            [PLAN, IDEATION, WORKER, MANAGE_DONE],
            config=RunnerConfig(max_tokens=25),
            reply_tokens=10,
        )

        result = runner.run("problema")

        assert result.status == "budget"
        assert result.tokens <= 30

    def test_max_tasks_truncates_plan(self, tmp_path):
        plan = "### PLAN\nx\n### TASKS\n" + "\n".join(f"- t{i}" for i in range(10)) + "\n"
        manage = (
            "### STATUS\ndone\n### TASKS\n"
            + "\n".join(f"- t{i}" for i in range(10))
            + "\n"
        )
        runner, ledger, _ = make_runner(
            tmp_path,
            [plan, IDEATION, WORKER, manage],
            config=RunnerConfig(max_tasks=3),
        )

        runner.run("problema")

        assert len(ledger.read_tasks()) == 3

    def test_provider_error_returns_infra(self, tmp_path):
        def provider(role, prompt):
            raise TimeoutError("boom")

        runner = Runner(
            ledger=Ledger(tmp_path / "ws"),
            spec=CODE_REPO,
            provider=provider,
            verifier=lambda: Verdict(ok=True),
        )

        result = runner.run("problema")

        assert result.status == "infra"
        assert "boom" in result.detail

    def test_preflight_ineligible_stops_before_plan(self, tmp_path):
        runner, _, provider = make_runner(tmp_path, [], preflight=lambda: "test-targeted")

        result = runner.run("problema")

        assert result.status == "ineligible"
        assert "test-targeted" in result.detail
        assert provider.roles == []

    def test_problem_md_and_base_sha_are_written(self, tmp_path):
        runner, ledger, _ = make_runner(
            tmp_path, [PLAN, IDEATION, WORKER, MANAGE_DONE], base_sha="abc123"
        )

        runner.run("problema")

        assert "problema" in ledger.read_text("problem.md")
        assert ledger.get_base_sha() == "abc123"

    def test_result_is_recorded(self, tmp_path):
        runner, ledger, _ = make_runner(tmp_path, [PLAN, IDEATION, WORKER, MANAGE_DONE])

        runner.run("problema")

        assert ledger.record_entries()[-1]["role"] == "result"

    def test_tamper_check_none_counts_as_tamper(self, tmp_path):
        tamper = iter([None, None])
        runner, _, _ = make_runner(
            tmp_path,
            [PLAN, IDEATION, WORKER, WORKER],
            tamper_check=lambda: next(tamper, False),
        )

        result = runner.run("problema")

        assert result.status == "protocol"
        assert "test-tamper" in result.detail

    def test_missing_tamper_check_is_reported(self, tmp_path):
        runner, _, _ = make_runner(tmp_path, [PLAN, IDEATION, WORKER, MANAGE_DONE])

        result = runner.run("problema")

        assert result.tamper_checked is False

    def test_restore_tests_called_on_tamper(self, tmp_path):
        calls = []
        tamper = iter([True, False])
        runner, _, _ = make_runner(
            tmp_path,
            [PLAN, IDEATION, WORKER, WORKER, MANAGE_DONE],
            tamper_check=lambda: next(tamper, False),
            restore_tests=lambda: calls.append(1),
        )

        runner.run("problema")

        assert calls == [1]

    def test_tampered_notes_are_not_persisted(self, tmp_path):
        fake_notes = "### NOTES\nFALSO\n### NEXT\nnada\n### STATUS\nsolved\n"
        tamper = iter([True, False])
        runner, ledger, _ = make_runner(
            tmp_path,
            [PLAN, IDEATION, fake_notes, WORKER, MANAGE_DONE],
            tamper_check=lambda: next(tamper, False),
        )

        runner.run("problema")

        assert "FALSO" not in ledger.read_text("notes.md")

    def test_manager_next_drives_the_next_worker(self, tmp_path):
        manage_next = "### STATUS\ncontinue\n### NEXT\nB: tests\n### TASKS\n- A\n"
        runner, _, provider = make_runner(
            tmp_path,
            [PLAN, IDEATION, WORKER, manage_next, WORKER, MANAGE_DONE],
            config=RunnerConfig(max_rounds=2),
        )

        runner.run("problema")

        assert "B: tests" in provider.prompts[4]

    def test_worker_status_reaches_manager_prompt(self, tmp_path):
        runner, _, provider = make_runner(tmp_path, [PLAN, IDEATION, WORKER, MANAGE_DONE])

        runner.run("problema")

        assert "solved" in provider.prompts[3]

    def test_plan_without_bullets_is_protocol_error(self, tmp_path):
        plan = "### PLAN\nx\n### TASKS\nSin tareas concretas.\n"
        runner, _, _ = make_runner(tmp_path, [plan, IDEATION, WORKER, MANAGE_DONE])

        result = runner.run("problema")

        assert result.status == "protocol"
        assert "no tasks" in result.detail

    def test_section_from_another_role_is_protocol_error(self, tmp_path):
        worker = "### NOTES\na\n### NEXT\nb\n### STATUS\nsolved\n### PLAN\ncolado\n"
        runner, _, _ = make_runner(
            tmp_path,
            [PLAN, IDEATION, worker, MANAGE_DONE],
            config=RunnerConfig(protocol_retries=0),
        )

        result = runner.run("problema")

        assert result.status == "protocol"
        assert "unexpected section: PLAN" in result.detail

    def test_protocol_error_is_retried_once(self, tmp_path):
        runner, _, provider = make_runner(
            tmp_path, [PLAN, IDEATION, "texto sin secciones", WORKER, MANAGE_DONE]
        )

        result = runner.run("problema")

        assert result.status == "done"
        assert provider.roles.count("worker") == 2

    def test_protocol_retry_exhausted_aborts(self, tmp_path):
        runner, _, _ = make_runner(
            tmp_path,
            [PLAN, IDEATION, "malo uno", "malo dos"],
            config=RunnerConfig(protocol_retries=1),
        )

        result = runner.run("problema")

        assert result.status == "protocol"

    def test_non_consecutive_tampers_do_not_abort(self, tmp_path):
        tamper = iter([True, False, True, False])
        runner, _, _ = make_runner(
            tmp_path,
            [
                PLAN,
                IDEATION,
                WORKER,
                WORKER,
                MANAGE_CONTINUE,
                WORKER,
                WORKER,
                MANAGE_DONE,
            ],
            config=RunnerConfig(max_rounds=4),
            tamper_check=lambda: next(tamper, False),
        )

        result = runner.run("problema")

        assert result.status == "done"

    def test_numbered_task_lines_are_parsed(self):
        from bytia_kode.orchestrator.runner import parse_task_lines

        assert parse_task_lines("1. uno\n2. dos\n") == ["uno", "dos"]

    def test_task_lines_inside_fence_are_ignored(self):
        from bytia_kode.orchestrator.runner import parse_task_lines

        assert parse_task_lines("```\n- ejemplo\n```\n- real\n") == ["real"]


class TestRound2Fixes:
    def test_verifier_exception_returns_infra(self, tmp_path):
        def verifier():
            raise TimeoutError("pytest timeout")

        runner, _, _ = make_runner(
            tmp_path, [PLAN, IDEATION, WORKER, MANAGE_DONE], verifier=verifier
        )

        result = runner.run("problema")

        assert result.status == "infra"
        assert "pytest timeout" in result.detail

    def test_preflight_exception_returns_infra(self, tmp_path):
        def preflight():
            raise OSError("sin repo")

        runner, _, _ = make_runner(tmp_path, [], preflight=preflight)

        result = runner.run("problema")

        assert result.status == "infra"
        assert "sin repo" in result.detail

    def test_restore_exception_returns_infra(self, tmp_path):
        tamper = iter([True, False])

        def restore():
            raise OSError("git roto")

        runner, _, _ = make_runner(
            tmp_path,
            [PLAN, IDEATION, WORKER, WORKER, MANAGE_DONE],
            tamper_check=lambda: next(tamper, False),
            restore_tests=restore,
        )

        result = runner.run("problema")

        assert result.status == "infra"
        assert "git roto" in result.detail

    def test_result_tokens_include_aborted_calls(self, tmp_path):
        runner, _, _ = make_runner(
            tmp_path,
            [PLAN, IDEATION, "malo uno", "malo dos"],
            config=RunnerConfig(protocol_retries=1),
            reply_tokens=10,
        )

        result = runner.run("problema")

        assert result.status == "protocol"
        assert result.tokens == 40

    def test_protocol_retries_from_config(self, monkeypatch):
        from bytia_kode.config import EscalationConfig
        from bytia_kode.orchestrator.runner import RunnerConfig

        monkeypatch.setenv("KODE_ESCALATION_PROTOCOL_RETRIES", "3")

        escalation = EscalationConfig()

        assert escalation.protocol_retries == 3
        assert RunnerConfig.from_escalation(escalation).protocol_retries == 3

    def test_tamper_check_error_is_recorded(self, tmp_path):
        def tamper_check():
            raise OSError("diff roto")

        runner, ledger, _ = make_runner(
            tmp_path,
            [PLAN, IDEATION, WORKER, WORKER],
            tamper_check=tamper_check,
        )

        result = runner.run("problema")

        assert result.status == "protocol"
        tamper_entries = [e for e in ledger.record_entries() if e["role"] == "tamper"]
        assert tamper_entries and "diff roto" in tamper_entries[0]["error"]

    def test_done_tasks_are_skipped_without_next(self, tmp_path):
        manage = "### STATUS\ncontinue\n### TASKS\n- A (done)\n- B\n"
        runner, _, provider = make_runner(
            tmp_path,
            [PLAN, IDEATION, WORKER, manage, WORKER, MANAGE_DONE],
            config=RunnerConfig(max_rounds=2),
        )

        runner.run("problema")

        assert "B" in provider.prompts[4]
        assert "A (done)" not in provider.prompts[4]

    def test_next_multiline_uses_first_line(self, tmp_path):
        manage = "### STATUS\ncontinue\n### NEXT\nB: tests\nmas detalle\n### TASKS\n- A\n"
        runner, _, provider = make_runner(
            tmp_path,
            [PLAN, IDEATION, WORKER, manage, WORKER, MANAGE_DONE],
            config=RunnerConfig(max_rounds=2),
        )

        runner.run("problema")

        assert "B: tests" in provider.prompts[4]
        assert "mas detalle" not in provider.prompts[4]

    def test_max_tasks_truncation_is_recorded(self, tmp_path):
        plan = "### PLAN\nx\n### TASKS\n" + "\n".join(f"- t{i}" for i in range(10)) + "\n"
        runner, ledger, _ = make_runner(
            tmp_path,
            [plan, IDEATION, WORKER, MANAGE_DONE],
            config=RunnerConfig(max_tasks=3),
        )

        runner.run("problema")

        entries = [e for e in ledger.record_entries() if e["role"] == "config"]
        assert entries and entries[0]["truncated_tasks"] == 7
