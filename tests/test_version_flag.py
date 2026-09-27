"""AST-23: `--version` imprime la versión (+ build id) y sale 0.

Cortesía para usuarios de pip: nunca arranca la TUI ni el bot. Gana el
primer flag — `--version --bot` imprime la versión igual que `--version`
solo (precedencia documentada en `__main__.py`).
"""
import re
import subprocess
import sys

import bytia_kode.__main__ as entry
from bytia_kode import __version__ as BASE_VERSION

_LABEL = r"\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?(?:\+[0-9a-f]{4,12})?"


def test_version_flag_prints_version_and_returns(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["bytia-kode", "--version"])
    entry.main()  # volver sin excepción = exit 0 para el console script
    out = capsys.readouterr().out.strip()
    assert out.startswith(BASE_VERSION)
    assert re.fullmatch(_LABEL, out), f"forma de versión inesperada: {out!r}"


def test_version_flag_never_starts_tui_or_bot(monkeypatch, capsys):
    import bytia_kode.tui as tui
    import bytia_kode.telegram.bot as bot

    calls = []
    monkeypatch.setattr(tui, "run_tui", lambda: calls.append("tui"))
    monkeypatch.setattr(bot, "main", lambda: calls.append("bot"))
    monkeypatch.setattr("sys.argv", ["bytia-kode", "--version"])
    entry.main()
    assert calls == []
    assert capsys.readouterr().out.strip()


def test_version_wins_when_bot_follows(monkeypatch, capsys):
    # --bot en segunda posición no cuenta: el dispatch sólo mira argv[1]
    import bytia_kode.telegram.bot as bot

    calls = []
    monkeypatch.setattr(bot, "main", lambda: calls.append("bot"))
    monkeypatch.setattr("sys.argv", ["bytia-kode", "--version", "--bot"])
    entry.main()
    assert calls == []
    assert capsys.readouterr().out.strip().startswith(BASE_VERSION)


def test_python_m_version_exits_zero():
    # Contrato de salida real, por el camino que usa pip (`python -m`).
    proc = subprocess.run(
        [sys.executable, "-m", "bytia_kode", "--version"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().startswith(BASE_VERSION)
