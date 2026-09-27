"""AST-20 (residuo C6): el build id `vX.Y.Z+<commit>` distingue builds.

Cubre los tres modos de instalación —editable (git en runtime), wheel/sdist
estampado en build time, PyPI sin estampa— más el caso sin git disponible,
la validación de basura y el cacheo por proceso (una sola resolución).
"""
import re
import subprocess

import pytest

from bytia_kode import __version__ as BASE_VERSION
from bytia_kode import _build_info, version_label


@pytest.fixture(autouse=True)
def _fresh_cache():
    _build_info.reset_cache()
    yield
    _build_info.reset_cache()


def _fake_pkg_dir(monkeypatch, tmp_path, *, site_packages: bool, stamp: str | None = None):
    """Sitúa el paquete en un directorio que imita el modo de instalación dado."""
    parent = tmp_path / ("site-packages" if site_packages else "checkout/src")
    pkg = parent / "bytia_kode"
    pkg.mkdir(parents=True)
    if stamp is not None:
        (pkg / "_commit.txt").write_text(stamp, encoding="utf-8")
    monkeypatch.setattr(_build_info, "_package_dir", lambda: pkg)
    return pkg


def _git_must_not_run(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("git no debe consultarse en este modo")
    monkeypatch.setattr(_build_info, "_runtime_commit", _boom)


# --- modo 1: editable — el paquete vive en el checkout, git en runtime ------

def test_editable_reads_runtime_git(monkeypatch, tmp_path):
    _fake_pkg_dir(monkeypatch, tmp_path, site_packages=False)
    monkeypatch.setattr(_build_info, "_runtime_commit", lambda: "60bac33")
    assert _build_info.short_commit() == "60bac33"
    assert version_label() == f"{BASE_VERSION}+60bac33"


def test_editable_without_git_degrades_to_plain_version(monkeypatch, tmp_path):
    _fake_pkg_dir(monkeypatch, tmp_path, site_packages=False)

    def _no_git(*args, **kwargs):
        raise FileNotFoundError("git no instalado")

    monkeypatch.setattr(_build_info.subprocess, "run", _no_git)
    assert _build_info.short_commit() is None
    assert version_label() == BASE_VERSION


def test_git_error_degrades_to_plain_version(monkeypatch, tmp_path):
    _fake_pkg_dir(monkeypatch, tmp_path, site_packages=False)
    monkeypatch.setattr(
        _build_info.subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess([], 128, stdout=""),
    )
    assert _build_info.short_commit() is None


def test_garbage_git_output_is_rejected(monkeypatch, tmp_path):
    _fake_pkg_dir(monkeypatch, tmp_path, site_packages=False)
    monkeypatch.setattr(
        _build_info.subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess([], 0, stdout="fatal: not a git repository"),
    )
    assert _build_info.short_commit() is None


# --- modo 2: wheel/sdist estampado en build time ----------------------------

def test_wheel_stamp_wins_and_git_is_not_consulted(monkeypatch, tmp_path):
    _fake_pkg_dir(monkeypatch, tmp_path, site_packages=True, stamp="60bac33\n")
    _git_must_not_run(monkeypatch)
    assert _build_info.short_commit() == "60bac33"
    assert version_label() == f"{BASE_VERSION}+60bac33"


def test_corrupt_stamp_is_ignored(monkeypatch, tmp_path):
    _fake_pkg_dir(monkeypatch, tmp_path, site_packages=True, stamp="not-a-hash")
    _git_must_not_run(monkeypatch)
    assert _build_info.short_commit() is None
    assert version_label() == BASE_VERSION


# --- modo 3: PyPI sin estampa ------------------------------------------------

def test_pypi_without_stamp_has_no_suffix(monkeypatch, tmp_path):
    _fake_pkg_dir(monkeypatch, tmp_path, site_packages=True)
    # Un venv puede vivir dentro de un repo ajeno: sin estampa, ahí no se
    # consulta git (el hash de ese repo no es el hash de este build).
    _git_must_not_run(monkeypatch)
    assert _build_info.short_commit() is None
    assert version_label() == BASE_VERSION


# --- coste: resolver una vez y cachear ---------------------------------------

def test_commit_is_resolved_once_per_process(monkeypatch, tmp_path):
    _fake_pkg_dir(monkeypatch, tmp_path, site_packages=False)
    calls = []

    def _count():
        calls.append(1)
        return "abc1234"

    monkeypatch.setattr(_build_info, "_runtime_commit", _count)
    assert _build_info.short_commit() == "abc1234"
    assert _build_info.short_commit() == "abc1234"
    assert version_label() == f"{BASE_VERSION}+abc1234"
    assert len(calls) == 1


# --- forma de la etiqueta y header de la TUI ---------------------------------

def test_version_label_shape():
    assert re.fullmatch(r"\d+\.\d+\.\d+a\d+(\+[0-9a-f]{4,12})?", version_label())


def test_tui_info_line_carries_build_id(monkeypatch):
    from bytia_kode import tui

    monkeypatch.setattr(tui, "version_label", lambda: "0.8.0a1+60bac33")
    line = tui._info_line(True)
    assert "v0.8.0a1+60bac33" in line
    assert "[green]B-KODE.md[/]" in line
    assert "Ctrl+P menu" in line
    assert "no B-KODE.md" in tui._info_line(False)
