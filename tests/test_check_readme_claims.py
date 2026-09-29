"""Tests del propio gate de claims del README (AST-33).

En CI el gate corre con red (sólo PyPI); aquí se ejercita en modo
--offline-pypi para mantener la suite hermética. Se fijan:

1. Verde: el gate pasa sobre el README real del repo (offline).
2. Fail cerrado: sobre una COPIA mutada del README, tres clases de claim
   falsa (default de config, enlace relativo roto, comando sin cubrir)
   rompen el gate citando la claim exacta — y luego la copia se descarta.
3. Parsers puros: heredocs del fence bash y slugs de anclas GitHub.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_readme_claims.py"
README = ROOT / "README.md"

spec = importlib.util.spec_from_file_location("check_readme_claims", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def _run_gate(readme: Path | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT), "--offline-pypi"]
    if readme is not None:
        cmd += ["--readme", str(readme)]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=600)


def test_gate_green_on_real_readme_offline():
    proc = _run_gate()
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    assert "0 FALLOS" in proc.stdout
    assert "GATE EN VERDE" in proc.stdout


def test_fail_closed_catches_false_claims(tmp_path):
    # TRES claims falsas en una sola copia: default de config mentiroso,
    # enlace relativo roto y comando nuevo sin cobertura en el gate.
    text = README.read_text(encoding="utf-8")
    text = text.replace("`gemma4:26b`", "`gemma4:99b`")
    text = text.replace(
        "- [Código de conducta](CODE_OF_CONDUCT.md)",
        "- [Código de conducta](CODE_OF_CONDUCT.md)\n- [Fantoche](docs/NO_EXISTE.md)",
    )
    text += "\n```bash\nmake sandwich\n```\n"
    mutated = tmp_path / "README_mutated.md"
    mutated.write_text(text, encoding="utf-8")

    proc = _run_gate(mutated)
    assert proc.returncode != 0, "claim falsa que el gate dejó pasar"
    assert "GATE EN ROJO" in proc.stdout
    # cada claim falsa citada con su nombre — no un error genérico
    assert "LOCAL_MODEL: README='gemma4:99b'" in proc.stdout
    assert "docs/NO_EXISTE.md" in proc.stdout
    assert "make sandwich" in proc.stdout


def test_bash_commands_skips_heredoc_bodies_and_comments():
    text = (
        "```bash\n"
        "cat > ~/.bytia-kode/.env << 'EOF'\n"
        "PROVIDER_API_KEY=not-needed\n"
        "EOF\n"
        "# comentario\n"
        "bytia-kode --version    # versión instalada y sale\n"
        "```\n"
    )
    assert gate.bash_commands(text) == [
        "cat > ~/.bytia-kode/.env << 'EOF'",
        "bytia-kode --version",
    ]


def test_github_slug_keeps_unicode_and_dashes():
    # en producción se recibe el texto del heading SIN los '###'
    assert gate.github_slug("Política de workspace") == "política-de-workspace"
    assert gate.github_slug("Instalación rápida (recomendada)") == "instalación-rápida-recomendada"


def test_section_extracts_body_until_same_level_heading():
    text = "## A\nuno\n### B\ndos\n## C\ntres\n"
    assert gate.section(text, "A", 2) == "\nuno\n### B\ndos\n"
