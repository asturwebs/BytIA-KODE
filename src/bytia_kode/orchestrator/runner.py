"""Bucle del orquestador (F1, T4a: flujo feliz + presupuestos).

Síncrono en F1: el provider y el verifier se inyectan. El bucle real de
KODE es async; la adaptación (Agent + verify.py reales) es F2.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from bytia_kode.orchestrator.prompts import ROLE_PROMPTS
from bytia_kode.orchestrator.protocol import parse_sections, validate_sections


@dataclass
class Reply:
    text: str
    tokens: int = 0


@dataclass
class Verdict:
    ok: bool
    detail: str = ""


@dataclass
class RunnerConfig:
    max_rounds: int = 4
    max_tasks: int = 8
    max_tokens: int = 200_000
    max_wallclock_s: float = 20 * 60


@dataclass
class RunResult:
    status: str
    rounds: int = 0
    tokens: int = 0
    detail: str = ""


def parse_task_lines(text: str) -> list[str]:
    tasks: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            task = stripped[2:].strip()
            if task:
                tasks.append(task)
    return tasks


class Runner:
    def __init__(self, *, ledger, spec, provider, verifier, config=None, clock=None):
        self.ledger = ledger
        self.spec = spec
        self.provider = provider
        self.verifier = verifier
        self.config = config or RunnerConfig()
        self.clock = clock or time.monotonic

    # -- llamadas ----------------------------------------------------------
    def _call(self, role: str, prompt: str, tokens: int) -> tuple[Reply, int]:
        reply = self.provider(role, prompt)
        self.ledger.append_record({"role": role, "tokens": reply.tokens})
        return reply, tokens + reply.tokens

    def _validate(self, role: str, parsed: dict[str, str]) -> list[str]:
        role_spec = self.spec.roles[role]
        required = list(role_spec.required)
        status = parsed.get("STATUS", "").strip().lower()
        if status and status != "done":
            required += role_spec.required_when_continuing
        allowed: set[str] = set()
        for spec in self.spec.roles.values():
            allowed.update(spec.required)
            allowed.update(spec.required_when_continuing)
        return validate_sections(
            parsed,
            tuple(required),
            allowed=tuple(sorted(allowed)),
            allowed_status=role_spec.allowed_status,
        )

    # -- prompts -----------------------------------------------------------
    def _plan_prompt(self, task_text: str) -> str:
        return f"{ROLE_PROMPTS['primary_plan']}\n\nPROBLEMA:\n{task_text}\n"

    def _ideation_prompt(self, task_text: str, plan: str) -> str:
        return f"{ROLE_PROMPTS['ideation']}\n\nPROBLEMA:\n{task_text}\n\nPLAN:\n{plan}\n"

    def _worker_prompt(self, task_text: str, task: str, notes: str) -> str:
        return (
            f"{ROLE_PROMPTS['worker']}\n\nPROBLEMA:\n{task_text}\n\n"
            f"TAREA ACTUAL:\n{task}\n\nNOTAS:\n{notes}\n"
        )

    def _manage_prompt(self, notes: str, tasks: list[str], verdict: Verdict) -> str:
        task_list = "\n".join(f"- {task}" for task in tasks)
        return (
            f"{ROLE_PROMPTS['primary_manage']}\n\nVEREDICTO DE TESTS: "
            f"{'OK' if verdict.ok else 'FALLO'} {verdict.detail}\n\n"
            f"TAREAS:\n{task_list}\n\nNOTAS:\n{notes}\n"
        )

    # -- bucle -------------------------------------------------------------
    def run(self, task_text: str) -> RunResult:
        start = self.clock()
        tokens = 0
        rounds = 0

        reply, tokens = self._call("primary_plan", self._plan_prompt(task_text), tokens)
        parsed = parse_sections(reply.text)
        errors = self._validate("primary_plan", parsed)
        if errors:
            return RunResult("protocol", tokens=tokens, detail="; ".join(errors))
        plan = parsed["PLAN"]
        self.ledger.write_text("plan.md", plan)
        tasks = parse_task_lines(parsed["TASKS"])
        self.ledger.write_tasks(tasks)

        reply, tokens = self._call("ideation", self._ideation_prompt(task_text, plan), tokens)
        parsed = parse_sections(reply.text)
        errors = self._validate("ideation", parsed)
        if errors:
            return RunResult("protocol", tokens=tokens, detail="; ".join(errors))
        notes = parsed["NOTES"]
        self.ledger.write_text("notes.md", notes)

        for round_no in range(1, self.config.max_rounds + 1):
            rounds = round_no
            if tokens >= self.config.max_tokens:
                return RunResult("budget", rounds=rounds, tokens=tokens)
            if self.clock() - start >= self.config.max_wallclock_s:
                return RunResult("budget", rounds=rounds, tokens=tokens)
            if not tasks:
                return RunResult("budget", rounds=rounds, tokens=tokens, detail="no tasks")

            task = tasks[0]
            reply, tokens = self._call(
                "worker", self._worker_prompt(task_text, task, notes), tokens
            )
            parsed = parse_sections(reply.text)
            errors = self._validate("worker", parsed)
            if errors:
                return RunResult(
                    "protocol", rounds=rounds, tokens=tokens, detail="; ".join(errors)
                )
            notes = parsed["NOTES"]
            self.ledger.write_text("notes.md", notes)

            verdict = self.verifier()
            reply, tokens = self._call(
                "primary_manage", self._manage_prompt(notes, tasks, verdict), tokens
            )
            parsed = parse_sections(reply.text)
            errors = self._validate("primary_manage", parsed)
            if errors:
                return RunResult(
                    "protocol", rounds=rounds, tokens=tokens, detail="; ".join(errors)
                )
            tasks = parse_task_lines(parsed.get("TASKS", "")) or tasks
            self.ledger.write_tasks(tasks)
            if parsed["STATUS"].strip().lower() == "done":
                return RunResult("done", rounds=rounds, tokens=tokens)

        return RunResult("budget", rounds=rounds, tokens=tokens)
