"""Ejecución de tests/build en el scratch (F2/T7).

El baseline de fallos preexistentes es la clave del veredicto: un test que
ya fallaba antes del worker no invalida la ronda; solo cuentan los fallos
NUEVOS. Timeout duro y salida recortada para el manager.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

_FAILED_LINE = re.compile(r"^FAILED\s+(\S+)")
_PASSED = re.compile(r"(\d+) passed")
_FAILED = re.compile(r"(\d+) failed")


@dataclass
class VerifyResult:
    ok: bool
    command: str
    exit_code: int | None
    passed: int = 0
    failed: int = 0
    new_failures: list[str] = field(default_factory=list)
    output_tail: str = ""
    error: str = ""


class Verifier:
    def __init__(
        self,
        *,
        command: str | None = None,
        timeout_s: float = 120.0,
        tail_lines: int = 40,
    ):
        self.command = command or os.getenv(
            "KODE_ESCALATION_VERIFY_CMD", "pytest -q --tb=no"
        )
        self.timeout_s = timeout_s
        self.tail_lines = tail_lines

    def _argv(self) -> list[str]:
        parts = shlex.split(self.command)
        if parts and parts[0] == "pytest":
            return [sys.executable, "-m", "pytest", *parts[1:]]
        return parts

    def _tail(self, text: str) -> str:
        return "\n".join(text.splitlines()[-self.tail_lines :])

    def _run(self, cwd: Path) -> VerifyResult:
        try:
            completed = subprocess.run(
                self._argv(),
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
        except subprocess.TimeoutExpired:
            return VerifyResult(
                ok=False,
                command=self.command,
                exit_code=None,
                error="timeout",
            )
        output = (completed.stdout or "") + (completed.stderr or "")
        failed_tests: list[str] = []
        for line in output.splitlines():
            match = _FAILED_LINE.match(line)
            if match:
                failed_tests.append(match.group(1))
        passed_match = _PASSED.search(output)
        failed_match = _FAILED.search(output)
        return VerifyResult(
            ok=completed.returncode == 0,
            command=self.command,
            exit_code=completed.returncode,
            passed=int(passed_match.group(1)) if passed_match else 0,
            failed=int(failed_match.group(1)) if failed_match else 0,
            new_failures=failed_tests,
            output_tail=self._tail(output),
        )

    def capture_baseline(self, cwd: Path) -> set[str]:
        return set(self._run(cwd).new_failures)

    def run(self, cwd: Path, baseline: set[str] | None = None) -> VerifyResult:
        result = self._run(cwd)
        if baseline is not None:
            new_failures = [t for t in result.new_failures if t not in baseline]
            result.new_failures = new_failures
            # Solo exit 1 es «tests rojos comparables»: 2 (interrupted),
            # 3 (internal), 4 (usage/conftest) y 5 (no tests) NO son verdes.
            result.ok = result.exit_code == 0 or (
                result.exit_code == 1 and not new_failures
            )
        return result
