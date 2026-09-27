"""AST-22: el camino canónico de instalación es PyPI, no el clone.

Guardas de deriva: install.sh instala desde PyPI sin clonar nada, el README
documenta ese camino, y el console script despacha `--bot` igual que
`python -m bytia_kode` (antes arrancaba la TUI en silencio).
"""
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = ROOT / "install.sh"
README = ROOT / "README.md"
PYPROJECT = ROOT / "pyproject.toml"


def _install_sh() -> str:
    return INSTALL_SH.read_text(encoding="utf-8")


# --- install.sh: instala desde PyPI, sin clone ni wrapper -------------------

def test_install_sh_installs_from_pypi():
    script = _install_sh()
    assert 'uv tool install --upgrade "$SPEC"' in script
    assert 'SPEC="bytia-kode"' in script


def test_install_sh_has_no_git_commands():
    # El clone/pull es desarrollo, no instalación. Se comprueban comandos
    # ejecutables, no comentarios: el script nombra el clone a propósito
    # para decir que ya NO es el camino.
    script = _install_sh()
    for cmd in ("git clone", "git pull", "git config"):
        assert re.search(rf"^\s*{re.escape(cmd)}\b", script, re.M) is None, cmd


def test_install_sh_configures_global_env():
    script = _install_sh()
    assert '"$KODE_HOME/.env"' in script  # ~/.bytia-kode/.env, preservado si existe
    assert "mkdir -p \"$SKILLS_HOME/vendor\"" in script
    assert "mkdir -p \"$SKILLS_HOME/user\"" in script


def test_install_sh_bootstraps_uv():
    script = _install_sh()
    assert "https://astral.sh/uv/install.sh" in script


# --- README: refleja el camino canónico -------------------------------------

def test_readme_documents_pypi_install():
    readme = README.read_text(encoding="utf-8")
    assert (
        "pip install bytia-kode" in readme
        or "uv tool install bytia-kode" in readme
    ), "README debe reflejar la instalación oficial desde PyPI"


# --- console script: entry point que despacha -------------------------------

def test_console_script_entry_point_dispatches():
    with PYPROJECT.open("rb") as fh:
        data = tomllib.load(fh)
    assert (
        data["project"]["scripts"]["bytia-kode"] == "bytia_kode.__main__:main"
    ), "el console script debe enrutar por __main__.main para despachar --bot"


def test_main_dispatches_bot_flag(monkeypatch):
    import bytia_kode.__main__ as entry
    import bytia_kode.telegram.bot as bot

    calls = []
    monkeypatch.setattr(bot, "main", lambda: calls.append("bot"))
    monkeypatch.setattr("sys.argv", ["bytia-kode", "--bot"])
    entry.main()
    assert calls == ["bot"]


def test_main_dispatches_tui_by_default(monkeypatch):
    import bytia_kode.__main__ as entry
    import bytia_kode.tui as tui

    calls = []
    monkeypatch.setattr(tui, "run_tui", lambda: calls.append("tui"))
    monkeypatch.setattr("sys.argv", ["bytia-kode"])
    entry.main()
    assert calls == ["tui"]


def test_main_ignores_bot_flag_in_other_position(monkeypatch):
    # --bot sólo cuenta como primer argumento, igual que el dispatch histórico
    # de __main__.py; en cualquier otra posición arranca la TUI.
    import bytia_kode.__main__ as entry
    import bytia_kode.tui as tui

    calls = []
    monkeypatch.setattr(tui, "run_tui", lambda: calls.append("tui"))
    monkeypatch.setattr("sys.argv", ["bytia-kode", "chat", "--bot"])
    entry.main()
    assert calls == ["tui"]
