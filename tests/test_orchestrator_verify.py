"""Contrato de verify.py (F2/T7).

Ejecuta pytest/build en el scratch con timeout y veredicto estructurado.
El baseline de fallos preexistentes es la clave: un test que ya fallaba antes
del worker no invalida la ronda; solo cuentan los fallos NUEVOS.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from bytia_kode.orchestrator.verify import Verifier


def write_test(directory: Path, name: str, body: str) -> None:
    (directory / name).write_text(textwrap.dedent(body), encoding="utf-8")


class TestGreenAndRed:
    def test_green_suite_is_ok(self, tmp_path):
        write_test(tmp_path, "test_ok.py", "def test_ok():\n    assert True\n")

        result = Verifier().run(tmp_path)

        assert result.ok is True
        assert result.exit_code == 0
        assert result.passed == 1
        assert result.failed == 0

    def test_red_suite_is_not_ok(self, tmp_path):
        write_test(tmp_path, "test_bad.py", "def test_bad():\n    assert False\n")

        result = Verifier().run(tmp_path)

        assert result.ok is False
        assert result.exit_code == 1
        assert result.failed == 1
        assert len(result.new_failures) == 1
        assert "test_bad" in result.new_failures[0]


class TestBaseline:
    def test_preexisting_failure_is_not_new(self, tmp_path):
        write_test(tmp_path, "test_bad.py", "def test_bad():\n    assert False\n")
        verifier = Verifier()
        baseline = verifier.capture_baseline(tmp_path)

        result = verifier.run(tmp_path, baseline=baseline)

        assert baseline
        assert result.ok is True
        assert result.new_failures == []

    def test_new_failure_is_reported(self, tmp_path):
        write_test(tmp_path, "test_ok.py", "def test_ok():\n    assert True\n")
        verifier = Verifier()
        baseline = verifier.capture_baseline(tmp_path)
        write_test(tmp_path, "test_new_bad.py", "def test_bad():\n    assert False\n")

        result = verifier.run(tmp_path, baseline=baseline)

        assert result.ok is False
        assert len(result.new_failures) == 1


class TestErrorsAndConfig:
    def test_timeout_is_error(self, tmp_path):
        verifier = Verifier(
            command=f'{sys.executable} -c "import time; time.sleep(5)"',
            timeout_s=0.5,
        )

        result = verifier.run(tmp_path)

        assert result.ok is False
        assert result.error == "timeout"
        assert result.exit_code is None

    def test_custom_command(self, tmp_path):
        verifier = Verifier(command=f'{sys.executable} -c "raise SystemExit(0)"')

        result = verifier.run(tmp_path)

        assert result.ok is True
        assert result.exit_code == 0

    def test_command_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KODE_ESCALATION_VERIFY_CMD", f'{sys.executable} -c "raise SystemExit(0)"')

        result = Verifier().run(tmp_path)

        assert result.ok is True

    def test_output_tail_is_limited(self, tmp_path):
        verifier = Verifier(
            command=f'{sys.executable} -c "print(chr(10).join(str(i) for i in range(200)))"',
            tail_lines=5,
        )

        result = verifier.run(tmp_path)

        assert len(result.output_tail.splitlines()) == 5
