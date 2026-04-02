"""BytIA KODE - Agentic coding CLI & Telegram bot"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _read_pyproject_version() -> str:
    try:
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        for line in pyproject.read_text(encoding="utf-8").splitlines():
            if line.startswith("version = "):
                return line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return "0.3.0"


try:
    __version__ = version("bytia-kode")
except PackageNotFoundError:
    __version__ = _read_pyproject_version()
