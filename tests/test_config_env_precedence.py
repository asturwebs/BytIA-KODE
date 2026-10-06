"""T4 (AST-15 O1-B): the global ~/.bytia-kode/.env must not stomp the project .env.

config.py loads CWD/.env first and then the global file with override=False,
so a value planted in the agent-writable global .env can no longer shadow the
project's configuration.
"""
import importlib
import os
from pathlib import Path

import pytest

from bytia_kode import config as config_module

_KEY = "BYTIA_T4_ENV_PRECEDENCE"


@pytest.fixture
def env_dirs(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / ".env").write_text(f"{_KEY}=project-wins\n")
    global_dir = tmp_path / "home" / ".bytia-kode"
    global_dir.mkdir(parents=True)
    (global_dir / ".env").write_text(f"{_KEY}=global-loses\n")
    monkeypatch.chdir(project)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    monkeypatch.delenv(_KEY, raising=False)


def test_global_env_does_not_override_project_dotenv(env_dirs):
    importlib.reload(config_module)  # re-runs module-level load_dotenv calls
    assert os.environ.get(_KEY) == "project-wins"


def test_global_env_fills_keys_the_project_does_not_set(tmp_path, monkeypatch, env_dirs):
    (tmp_path / "home" / ".bytia-kode" / ".env").write_text(
        f"{_KEY}=global-loses\nBYTIA_T4_GLOBAL_ONLY=present\n"
    )
    importlib.reload(config_module)
    assert os.environ.get(_KEY) == "project-wins"
    assert os.environ.get("BYTIA_T4_GLOBAL_ONLY") == "present"
    os.environ.pop("BYTIA_T4_GLOBAL_ONLY", None)


def test_project_empty_declaration_blocks_global_fill(tmp_path, monkeypatch):
    """AST-36: `KEY=` (vacío) en el .env del proyecto cuenta como DECLARADA —
    el global no puede rellenarla. Es el mecanismo exacto del incidente de los
    6.253 restarts del bot: plantilla copiada con `TELEGRAM_BOT_TOKEN=` en
    blanco mientras el global tenía el token real. Este test fija la
    semántica para que .env.example siga trayendo los placeholders comentados
    (gate scripts/check_env_example.py)."""
    project = tmp_path / "project"
    project.mkdir()
    (project / ".env").write_text(f"{_KEY}=\n")  # declarada VACÍA
    global_dir = tmp_path / "home" / ".bytia-kode"
    global_dir.mkdir(parents=True)
    (global_dir / ".env").write_text(f"{_KEY}=global-real-token\n")
    monkeypatch.chdir(project)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    monkeypatch.delenv(_KEY, raising=False)

    importlib.reload(config_module)

    # La declaración vacía del proyecto GANA al valor real del global: por eso
    # la plantilla no debe declarar nada vacío, y la precedencia NO se toca
    # (es la misma protección T4 del test de arriba, vista desde el otro lado).
    assert os.environ.get(_KEY) == ""
