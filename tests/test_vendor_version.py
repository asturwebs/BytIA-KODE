"""AST-23: `.vendor-version` lleva la versión real de la instalación.

En site-packages no hay pyproject.toml: la versión debe salir de
`importlib.metadata` (dist-info). Sin eso, toda instalación de PyPI escribía
"unknown" y el auto-reseed por cambio de versión nunca disparaba — las
skills vendor actualizadas no llegaban a los upgrades.
"""
import importlib.metadata
import shutil
import tomllib
from pathlib import Path

import bytia_kode.config as config
from bytia_kode.config import AppConfig

VENDOR_SKILLS = {"bytia-constitution", "bytia-memory", "graphify", "skills-manager"}
ROOT = Path(__file__).resolve().parents[1]


def _app(tmp_path, monkeypatch) -> AppConfig:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "home"))
    return AppConfig()


def test_package_version_comes_from_installed_metadata(tmp_path, monkeypatch):
    # El entorno de test tiene el paquete instalado (editable / uv run): esa
    # ES la verdad que debe verse — nunca "unknown" con metadata disponible.
    app = _app(tmp_path, monkeypatch)
    installed = importlib.metadata.version("bytia-kode")
    assert app._get_package_version() == installed


def test_fallback_to_pyproject_when_metadata_missing(tmp_path, monkeypatch):
    def _missing(name):
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(config.importlib.metadata, "version", _missing)
    app = _app(tmp_path, monkeypatch)
    # Sin dist-info, queda el pyproject del checkout (fuente sin instalar).
    # Se lee directo del archivo — la metadata instalada puede quedar vieja
    # entre el bump y el re-sync del entorno (lección AST-21).
    with (ROOT / "pyproject.toml").open("rb") as fh:
        expected = tomllib.load(fh)["project"]["version"]
    assert app._get_package_version() == expected


def test_vendor_version_file_carries_real_version(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    stamp = app.skills_dir / "vendor" / ".vendor-version"
    assert stamp.read_text(encoding="utf-8").strip() == importlib.metadata.version(
        "bytia-kode"
    )
    assert app.vendor_skills_installed is True
    seeded = {p.name for p in (app.skills_dir / "vendor").iterdir() if p.is_dir()}
    assert VENDOR_SKILLS <= seeded


def test_reseed_fires_when_installed_version_changes(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    vendor = app.skills_dir / "vendor"

    # Simula una instalación anterior: sello viejo y una skill borrada.
    (vendor / ".vendor-version").write_text("0.0.1", encoding="utf-8")
    shutil.rmtree(vendor / "graphify")

    app2 = _app(tmp_path, monkeypatch)
    assert app2.vendor_skills_installed is True
    assert (vendor / ".vendor-version").read_text(encoding="utf-8").strip() == (
        importlib.metadata.version("bytia-kode")
    )
    seeded = {p.name for p in vendor.iterdir() if p.is_dir()}
    assert VENDOR_SKILLS <= seeded, "el upgrade debe restaurar las skills vendor"
