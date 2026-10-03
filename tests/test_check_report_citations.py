"""Tests del propio gate de citas SHA de reports/ (AST-35).

En CI el gate corre como paso de workflow; aquí se fija su contrato de
2 criterios (resuelve / anotada — nota de diseño de la PI, sin whitelist
de patrones):

1. Verde sobre los reports reales del repo.
2. Fail cerrado: una cita SHA sin resolver y sin anotar rompe el gate
   citando fichero:línea y token — y con el sufijo `@ws` pasa, así que la
   convención de anotación está cubierta por los dos lados.
3. La rama de resolución se ejercita de verdad: en un repo efímero con un
   commit real, el sha de ese commit resuelve y entra por la clase
   "resuelve", mientras que un sha inventado cae.
4. Sin atajo por forma: un id de mock se salva declarado con causa, pero
   un decimal NO declarado en línea con MagicMock cae igual — el token no
   pasa por git solo por parecerse a un mock. Y el límite fail-cerrado de
   fechas compactas.
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


def test_declared_mock_id_passes_with_cause(tmp_path):
    """El id de mock pasa por DECLARED_CITATIONS con causa, no por forma.

    Los 10 ids de mock de las tablas QA/DEVOPS están declarados en el gate;
    éste es el contrato mismo: declarado → verde con causa en el inventario.
    """
    # 138477722887104 es un id de mock real, declarado en DECLARED_CITATIONS.
    reports = _write_report(
        tmp_path, "MagicMock/mock.data_dir.__truediv__()/138477722887104\n"
    )
    proc = _run_gate("--reports-dir", str(reports))
    assert proc.returncode == 0, proc.stdout[-3000:]
    assert "138477722887104" in proc.stdout
    assert "MagicMock" in proc.stdout  # la causa viaja en el inventario


def test_undeclared_decimal_on_mock_line_still_fails(tmp_path):
    """Sin atajo por forma: un decimal NO declarado cae aunque la línea diga MagicMock.

    Es la fragilidad que la nota de la PI apuntaba sobre la whitelist de
    patrones: clasificar por forma sin preguntarle a git. Con 2 criterios
    el único camino de un token sin resolver es anotarlo con causa.
    """
    reports = _write_report(
        tmp_path, "MagicMock/mock.data_dir.__truediv__()/998877665544332\n"
    )
    proc = _run_gate("--reports-dir", str(reports))
    assert proc.returncode != 0, "decimal no declarado que el gate dejó pasar"
    assert "998877665544332" in proc.stdout and "GATE EN ROJO" in proc.stdout


def test_compact_date_is_fail_closed_not_ignored(tmp_path):
    """Una fecha AAAAMMDD es cita hasta que se anota: no se salda en silencio.

    `20991231` no está declarada (la del bundle del rewrite, `20261003`, sí —
    ver test siguiente): cualquier otra fecha cae y pide causa.
    """
    assert gate.SHA_RE.findall("`20991231`") == ["20991231"]
    assert "20991231" not in gate.DECLARED_CITATIONS
    reports = _write_report(tmp_path, "Ver el addendum `20991231`.\n")
    proc = _run_gate("--reports-dir", str(reports))
    assert proc.returncode != 0, "fecha sin anotar que el gate dejó pasar"
    assert "20991231" in proc.stdout and "GATE EN ROJO" in proc.stdout


def test_corpus_residual_is_pre_registered_with_cause():
    """El residual del corpus (addendum AST-34) está declarado con causa.

    Los 4 stamps de release pre-rewrite no resuelven en ningún clon (verificado
    con git cat-file en AST-35) y la fecha `20261003` vive dentro del nombre
    literal del bundle — literales citados donde un sufijo falsearía el texto.
    Pre-registrados → cuando el addendum entre en reports/, el gate pasa sin
    tocar el documento.
    """
    for token in ("2521890", "91fb426", "64ce5c9", "7ee7b88"):
        klass, cause = gate.DECLARED_CITATIONS[token]
        assert klass == "bundle", (token, klass)
        assert "stamp" in cause, (token, cause)
    klass, cause = gate.DECLARED_CITATIONS["20261003"]
    assert klass == "nocommit" and "fecha" in cause
