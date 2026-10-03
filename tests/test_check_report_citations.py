"""Tests del propio gate de citas SHA de reports/ (AST-35).

En CI el gate corre como paso de workflow; aquí se fija su contrato:

1. Verde sobre los reports reales del repo.
2. Fail cerrado: una cita SHA sin resolver y sin anotar rompe el gate
   citando fichero:línea y token — y con el sufijo `@ws` pasa, así que la
   convención de anotación está cubierta por los dos lados.
3. La rama de resolución se ejercita de verdad: en un repo efímero con un
   commit real, el sha de ese commit resuelve y entra por la clase
   "resuelve", mientras que un sha inventado cae.
4. Patrones de no-commit (id de MagicMock, fragmento de UUID) y el límite
   fail-cado de fechas compactas.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_report_citations.py"

spec = importlib.util.spec_from_file_location("check_report_citations", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def _run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=ROOT, timeout=300,
    )


def test_gate_green_on_real_reports():
    proc = _run_gate()
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    assert "0 FALLOS" in proc.stdout
    assert "GATE EN VERDE" in proc.stdout
    # El inventario es por clase con los tokens, no un conteo de hex.
    assert "INVENTARIO POR CLASE" in proc.stdout
    assert "@ws:" in proc.stdout and "@bundle:" in proc.stdout
    assert "git cat-file:" in proc.stdout  # git se ejercita aunque todo esté anotado


def _write_report(tmp_path: Path, body: str) -> Path:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "copia.md").write_text(body, encoding="utf-8")
    return reports


def test_fail_closed_on_undeclared_sha(tmp_path):
    reports = _write_report(tmp_path, "Verificado en `c0ffee1` (commit del bot).\n")
    proc = _run_gate("--reports-dir", str(reports))
    assert proc.returncode != 0, "cita sin anotar que el gate dejó pasar"
    assert "GATE EN ROJO" in proc.stdout
    assert "copia.md:1" in proc.stdout and "c0ffee1" in proc.stdout
    # El mensaje enseña las dos vías de escape.
    assert "c0ffee1@ws" in proc.stdout and "DECLARED_CITATIONS" in proc.stdout


def test_suffix_annotation_passes(tmp_path):
    reports = _write_report(tmp_path, "Verificado en `c0ffee1@ws` (hash de workspace).\n")
    proc = _run_gate("--reports-dir", str(reports))
    assert proc.returncode == 0, proc.stdout[-3000:]
    assert "GATE EN VERDE" in proc.stdout


def test_resolution_branch_on_a_real_commit(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "fichero.txt").write_text("hola\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "fichero.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "base"],
        check=True,
    )
    sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--short=7", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    reports = _write_report(tmp_path, f"Cambio en `{sha}`.\n")
    proc = _run_gate("--repo", str(repo), "--reports-dir", str(reports))
    assert proc.returncode == 0, proc.stdout[-3000:]
    # El sha entra por la clase "resuelve" con sus citas — no declarado, no patrón.
    assert "✔ resuelve: 1 tokens" in proc.stdout
    assert f"{sha}  →  copia.md:1" in proc.stdout
    assert "GATE EN VERDE" in proc.stdout


def test_resolution_branch_fails_on_invented_sha(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "--allow-empty", "-m", "base"],
        check=True,
    )
    # `facade7` tiene forma de SHA y no es ancestro de nada: tiene que caer.
    reports = _write_report(tmp_path, "Cambio en `facade7`.\n")
    proc = _run_gate("--repo", str(repo), "--reports-dir", str(reports))
    assert proc.returncode != 0
    assert "facade7" in proc.stdout and "GATE EN ROJO" in proc.stdout


def test_pattern_non_commit_mocks_and_uuid():
    line = "MagicMock/mock.data_dir.__truediv__()/138477722887104"
    assert gate.pattern_non_commit("138477722887104", line, line.index("138")) is not None

    uuid_line = "| `41962dab-71fc-4101-8596-6666f530b1eb` | AST-8 |"
    start = uuid_line.index("41962dab")
    assert gate.pattern_non_commit("41962dab", uuid_line, start) is not None
    start = uuid_line.index("6666f530b1eb")
    assert gate.pattern_non_commit("6666f530b1eb", uuid_line, start) is not None

    # Un sha de commit en prosa no casa con ningún patrón.
    prose = "el botón de audio vuelve a `768d3ff`"
    assert gate.pattern_non_commit("768d3ff", prose, prose.index("768")) is None


def test_compact_date_is_fail_closed_not_ignored():
    """Una fecha AAAAMMDD es cita hasta que se anota: no se salda en silencio."""
    hits_before = gate.SHA_RE.findall("`20261003`")
    assert hits_before == ["20261003"]
    line = "Ver el addendum `20261003`"
    assert gate.pattern_non_commit("20261003", line, line.index("2026")) is None
