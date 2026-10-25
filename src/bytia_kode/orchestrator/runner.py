"""Bucle del orquestador (F1).

Síncrono en F1: provider, verifier, tamper_check y restore_tests se inyectan.
Presupuestos duros (se comprueban antes de CADA llamada), estados
`protocol` / `budget` / `infra` / `ineligible` / `done`, y registro completo
en ``record.jsonl`` (incluida la entrada terminal ``result``).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable

from bytia_kode.orchestrator.prompts import ROLE_PROMPTS
from bytia_kode.orchestrator.protocol import parse_sections, validate_sections


@dataclass
class Reply:
    text: str
    tokens: int = 0  # prompt + completion: el presupuesto es total


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
    protocol_retries: int = 1

    @classmethod
    def from_escalation(cls, escalation) -> "RunnerConfig":
        """Puente único con las claves KODE_ESCALATION_* (F2)."""
        return cls(
            max_rounds=escalation.max_rounds,
            max_tasks=escalation.max_tasks,
            max_tokens=escalation.max_tokens,
            max_wallclock_s=escalation.max_wallclock_min * 60,
            protocol_retries=escalation.protocol_retries,
        )


@dataclass
class RunResult:
    status: str
    rounds: int = 0
    tokens: int = 0
    detail: str = ""
    tamper_checked: bool = True


class _BudgetExceeded(Exception):
    pass


class _ProviderError(Exception):
    def __init__(self, detail: str, tokens: int):
        super().__init__(detail)
        self.tokens = tokens


class _ProtocolError(Exception):
    def __init__(self, detail: str, tokens: int):
        super().__init__(detail)
        self.tokens = tokens


def parse_task_lines(text: str) -> list[str]:
    """Tareas en bullets (`- x`, `* x`) o numeradas (`1. x`), fuera de fences."""
    tasks: list[str] = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if stripped.startswith(("- ", "* ")):
            task = stripped[2:].strip()
            if task:
                tasks.append(task)
            continue
        match = re.match(r"^\d+\.\s+(.*\S)\s*$", stripped)
        if match:
            tasks.append(match.group(1))
    return tasks


class Runner:
    def __init__(
        self,
        *,
        ledger,
        spec,
        provider: Callable[[str, str], Reply],
        verifier: Callable[[], Verdict],
        config: RunnerConfig | None = None,
        clock: Callable[[], float] | None = None,
        tamper_check: Callable[[], bool | None] | None = None,
        restore_tests: Callable[[], None] | None = None,
        preflight: Callable[[], str | None] | None = None,
        base_sha: str | None = None,
    ):
        self.ledger = ledger
        self.spec = spec
        self.provider = provider
        self.verifier = verifier
        self.config = config or RunnerConfig()
        self.clock = clock or time.monotonic
        self.tamper_check = tamper_check
        self.restore_tests = restore_tests
        self.preflight = preflight
        self.base_sha = base_sha

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _status(parsed: dict[str, str]) -> str:
        raw = parsed.get("STATUS", "").strip()
        return raw.split()[0].lower() if raw else ""

    def _check_budget(self, tokens: int, start: float) -> None:
        if tokens >= self.config.max_tokens:
            raise _BudgetExceeded
        if self.clock() - start >= self.config.max_wallclock_s:
            raise _BudgetExceeded

    def _call(
        self, role: str, prompt: str, tokens: int, start: float, round_no: int = 0
    ) -> tuple[Reply, int]:
        self._check_budget(tokens, start)
        try:
            reply = self.provider(role, prompt)
        except Exception as exc:  # noqa: BLE001 - se convierte en estado infra
            self.ledger.append_record(
                {"role": role, "round": round_no, "error": str(exc)}
            )
            raise _ProviderError(str(exc), tokens) from exc
        self.ledger.append_record(
            {"role": role, "round": round_no, "tokens": reply.tokens}
        )
        return reply, tokens + reply.tokens

    def _validate(self, role: str, parsed: dict[str, str]) -> list[str]:
        role_spec = self.spec.roles[role]
        allowed = (
            set(role_spec.required)
            | set(role_spec.recommended_when_continuing)
            | set(role_spec.allowed_extra)
        )
        return validate_sections(
            parsed,
            role_spec.required,
            allowed=tuple(sorted(allowed)),
            allowed_status=role_spec.allowed_status,
        )

    def _request(
        self, role: str, prompt: str, tokens: int, start: float, round_no: int = 0
    ) -> tuple[dict[str, str], int]:
        """Llamada con validación y reintento correctivo (C6: parser tolerante)."""
        attempt = 0
        current_prompt = prompt
        while True:
            reply, tokens = self._call(role, current_prompt, tokens, start, round_no)
            parsed = parse_sections(reply.text)
            errors = self._validate(role, parsed)
            if not errors:
                return parsed, tokens
            if attempt >= self.config.protocol_retries:
                raise _ProtocolError("; ".join(errors), tokens)
            attempt += 1
            current_prompt = (
                f"{prompt}\n\nTu respuesta anterior no cumplió el protocolo "
                f"({'; '.join(errors)}). Responde de nuevo SOLO con las secciones requeridas."
            )

    @staticmethod
    def _first_pending(tasks: list[str]) -> str | None:
        for task in tasks:
            if "(done)" not in task.lower():
                return task
        return tasks[0] if tasks else None

    @staticmethod
    def _next_line(parsed: dict[str, str]) -> str | None:
        for line in parsed.get("NEXT", "").splitlines():
            if line.strip():
                return line.strip()
        return None

    def _truncate(self, tasks: list[str], round_no: int = 0) -> list[str]:
        if len(tasks) > self.config.max_tasks:
            self.ledger.append_record(
                {
                    "role": "config",
                    "round": round_no,
                    "truncated_tasks": len(tasks) - self.config.max_tasks,
                }
            )
        return tasks[: self.config.max_tasks]

    # -- prompts -----------------------------------------------------------
    def _plan_prompt(self, task_text: str) -> str:
        return f"{ROLE_PROMPTS['primary_plan']}\n\nPROBLEMA:\n{task_text}\n"

    def _ideation_prompt(self, task_text: str) -> str:
        # Sin el PLAN en el contexto: el modelo local lo repetía como sección
        # en su respuesta (verificado en el e2e real con qwen38-160k).
        return f"{ROLE_PROMPTS['ideation']}\n\nPROBLEMA:\n{task_text}\n"

    def _worker_prompt(self, task_text: str, task: str, notes: str) -> str:
        return (
            f"{ROLE_PROMPTS['worker']}\n\nPROBLEMA:\n{task_text}\n\n"
            f"TAREA ACTUAL:\n{task}\n\nNOTAS:\n{notes}\n"
        )

    def _manage_prompt(
        self,
        notes: str,
        tasks: list[str],
        verdict: Verdict,
        worker_status: str,
        worker_next: str,
    ) -> str:
        task_list = "\n".join(f"- {task}" for task in tasks)
        return (
            f"{ROLE_PROMPTS['primary_manage']}\n\nVEREDICTO DE TESTS: "
            f"{'OK' if verdict.ok else 'FALLO'} {verdict.detail}\n\n"
            f"ULTIMO WORKER: STATUS {worker_status or '?'} · NEXT {worker_next or '-'}\n\n"
            f"TAREAS:\n{task_list}\n\nNOTAS:\n{notes}\n"
        )

    # -- bucle -------------------------------------------------------------
    def run(self, task_text: str) -> RunResult:
        start = self.clock()
        tokens = 0
        rounds = 0
        next_task: str | None = None

        def finish(result: RunResult) -> RunResult:
            self.ledger.append_record(
                {
                    "role": "result",
                    "status": result.status,
                    "rounds": result.rounds,
                    "tokens": result.tokens,
                }
            )
            result.tamper_checked = self.tamper_check is not None
            return result

        try:
            if self.preflight is not None:
                reason = self.preflight()
                if reason:
                    return finish(RunResult("ineligible", detail=str(reason)))

            self.ledger.write_text("problem.md", task_text)
            if self.base_sha:
                self.ledger.set_base_sha(self.base_sha)

            parsed, tokens = self._request(
                "primary_plan", self._plan_prompt(task_text), tokens, start
            )
            plan = parsed["PLAN"]
            self.ledger.write_text("plan.md", plan)
            tasks = self._truncate(parse_task_lines(parsed["TASKS"]))
            if not tasks:
                return finish(
                    RunResult("protocol", tokens=tokens, detail="no tasks")
                )
            self.ledger.write_tasks(tasks)

            parsed, tokens = self._request(
                "ideation", self._ideation_prompt(task_text), tokens, start
            )
            notes = parsed["NOTES"]
            self.ledger.write_text("notes.md", notes)

            invalid_streak = 0
            for round_no in range(1, self.config.max_rounds + 1):
                rounds = round_no
                if not tasks and next_task is None:
                    return finish(
                        RunResult(
                            "budget", rounds=rounds, tokens=tokens, detail="no tasks"
                        )
                    )
                task = next_task or self._first_pending(tasks)
                next_task = None

                parsed, tokens = self._request(
                    "worker",
                    self._worker_prompt(task_text, task, notes),
                    tokens,
                    start,
                    round_no,
                )

                tampered = False
                if self.tamper_check is not None:
                    try:
                        verdict_tamper = self.tamper_check()
                    except Exception as exc:  # noqa: BLE001 - fail-closed
                        self.ledger.append_record(
                            {"role": "tamper", "round": round_no, "error": str(exc)}
                        )
                        verdict_tamper = None
                    tampered = verdict_tamper is not False
                if tampered:
                    invalid_streak += 1
                    if self.restore_tests is not None:
                        self.restore_tests()
                    self.ledger.append_record({"role": "tamper", "round": round_no})
                    if invalid_streak >= 2:
                        return finish(
                            RunResult(
                                "protocol",
                                rounds=rounds,
                                tokens=tokens,
                                detail="test-tamper",
                            )
                        )
                    continue
                invalid_streak = 0

                notes = parsed["NOTES"]
                self.ledger.write_text("notes.md", notes)

                verdict = self.verifier()
                parsed_manage, tokens = self._request(
                    "primary_manage",
                    self._manage_prompt(
                        notes, tasks, verdict, self._status(parsed), parsed.get("NEXT", "")
                    ),
                    tokens,
                    start,
                    round_no,
                )
                tasks = (
                    self._truncate(
                        parse_task_lines(parsed_manage.get("TASKS", "")), round_no
                    )
                    or tasks
                )
                self.ledger.write_tasks(tasks)
                status = self._status(parsed_manage)
                if status == "done" and not verdict.ok:
                    status = "continue"
                if status == "done":
                    return finish(RunResult("done", rounds=rounds, tokens=tokens))
                next_task = self._next_line(parsed_manage)

            return finish(RunResult("budget", rounds=rounds, tokens=tokens))
        except _BudgetExceeded:
            return finish(RunResult("budget", rounds=rounds, tokens=tokens))
        except _ProtocolError as exc:
            return finish(
                RunResult("protocol", rounds=rounds, tokens=exc.tokens, detail=str(exc))
            )
        except _ProviderError as exc:
            return finish(
                RunResult("infra", rounds=rounds, tokens=exc.tokens, detail=str(exc))
            )
        except Exception as exc:  # noqa: BLE001 - seams y bugs nunca desnudos
            return finish(
                RunResult(
                    "infra",
                    rounds=rounds,
                    tokens=tokens,
                    detail=f"bug: {type(exc).__name__}: {exc}",
                )
            )
