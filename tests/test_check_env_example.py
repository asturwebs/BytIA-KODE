"""Tests del propio gate de plantilla .env.example (AST-36).

1. Verde: el gate pasa sobre la plantilla real del repo — la que llevó al
   incidente de los 6.253 restarts ya no declara nada vacío.
2. Fail cerrado: placeholders vacíos descomentados (forma literal del issue,
   vacío entrecomillado, espacios alrededor del `=`) rompen el gate citando
   línea y variable.
3. La forma comentada (`# VAR=`) — la que la plantilla usa ahora — pasa.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_env_example.py"
TEMPLATE = ROOT / ".env.example"


def _run_gate(template: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--template", str(template)],
        capture_output=True, text=True, cwd=ROOT, timeout=120,
    )


def test_gate_green_on_real_template():
    proc = _run_gate(TEMPLATE)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    assert "GATE EN VERDE" in proc.stdout


def test_fail_closed_on_empty_placeholder(tmp_path):
    # forma literal del criterio del issue: ^[A-Z_]+=$ descomentada
    template = tmp_path / "env"
    template.write_text("PROVIDER_MODEL=auto\nTELEGRAM_BOT_TOKEN=\n", encoding="utf-8")
    proc = _run_gate(template)
    assert proc.returncode != 0, "placeholder vacío que el gate dejó pasar"
    assert "GATE EN ROJO" in proc.stdout
    # citado con línea y variable — no un error genérico
    assert "env:2" in proc.stdout
    assert "TELEGRAM_BOT_TOKEN" in proc.stdout


def test_quoted_empty_and_spacing_also_flagged(tmp_path):
    template = tmp_path / "env"
    template.write_text('LOG_FILE=""\nEXTRA_BINARIES =\nDEEPSEEK_API_KEY=\'\'\n', encoding="utf-8")
    proc = _run_gate(template)
    assert proc.returncode != 0
    for var in ("LOG_FILE", "EXTRA_BINARIES", "DEEPSEEK_API_KEY"):
        assert var in proc.stdout


def test_digit_vars_covered(tmp_path):
    # el regex del issue (`^[A-Z_]+=$`) no atrapa nombres con dígitos; el gate sí
    template = tmp_path / "env"
    template.write_text("GPT4_API_KEY=\n", encoding="utf-8")
    proc = _run_gate(template)
    assert proc.returncode != 0
    assert "GPT4_API_KEY" in proc.stdout


def test_commented_placeholders_pass(tmp_path):
    template = tmp_path / "env"
    template.write_text(
        "# TELEGRAM_BOT_TOKEN=\nPROVIDER_MODEL=auto\n  # LOG_FILE=\n", encoding="utf-8"
    )
    proc = _run_gate(template)
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
