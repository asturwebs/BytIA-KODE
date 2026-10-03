"""Anexo DEVOPS: la versión nunca se inventa.

`_read_pyproject_version()` es el último recurso de `__version__`, pensado
para fuente sin instalar (sin `dist-info`). Devolvía el número muerto
`"0.3.0"`, que acababa impreso en el header del TUI y en el menú del bot
mintiendo sobre la versión real. Ahora degrada a `"unknown"`: honesto y
detectable por quien lo lea.
"""
import bytia_kode


def _point_module_at(monkeypatch, tmp_path):
    """Sitúa `__file__` en ``tmp_path/src/bytia_kode/``, sin crear nada."""
    target = tmp_path / "src" / "bytia_kode" / "__init__.py"
    monkeypatch.setattr(bytia_kode, "__file__", str(target))


def test_version_read_from_checkout_pyproject(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "bytia-kode"\nversion = "9.9.9"\n', encoding="utf-8"
    )
    _point_module_at(monkeypatch, tmp_path)
    assert bytia_kode._read_pyproject_version() == "9.9.9"


def test_pyproject_without_version_line_does_not_invent_one(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "bytia-kode"\n', encoding="utf-8"
    )
    _point_module_at(monkeypatch, tmp_path)
    assert bytia_kode._read_pyproject_version() == "unknown"


def test_missing_pyproject_never_returns_the_stale_number(monkeypatch, tmp_path):
    _point_module_at(monkeypatch, tmp_path)
    assert bytia_kode._read_pyproject_version() == "unknown"


def test_unreadable_pyproject_degrades_without_raising(monkeypatch, tmp_path):
    # Un directorio con ese nombre no se puede leer como fichero: la rama
    # `except` debe tragarse el error y no propagarlo al arranque.
    (tmp_path / "pyproject.toml").mkdir()
    _point_module_at(monkeypatch, tmp_path)
    assert bytia_kode._read_pyproject_version() == "unknown"


def test_installed_package_never_uses_the_fallback():
    # En un entorno con la distribución instalada, la verdad viene de
    # `importlib.metadata` y el fallback no se consulta. Si esto falla, el
    # venv de test no tiene el paquete instalado.
    from importlib.metadata import version

    assert version("bytia-kode") == bytia_kode.__version__
