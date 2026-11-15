"""Tests del guard de tamaño de resultados de herramientas.

Incidente 2026-11-15: un file_read de 201 KB agotó la ventana de contexto.
El guard recorta cabeza+cola y deja el original en disco.
"""
import os

import pytest

from bytia_kode.tools.output_guard import (
    DEFAULT_MAX_CHARS,
    guard_tool_output,
    max_chars,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("KODE_MAX_TOOL_RESULT_CHARS", raising=False)


class TestUnderLimit:
    def test_small_output_is_untouched(self, tmp_path):
        text = "hola mundo"
        assert guard_tool_output(text, "bash", data_dir=tmp_path) == text
        assert not (tmp_path / "tool-results").exists()

    def test_exactly_at_limit_is_untouched(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KODE_MAX_TOOL_RESULT_CHARS", "100")
        text = "x" * 100
        assert guard_tool_output(text, "bash", data_dir=tmp_path) == text


class TestOverLimit:
    def test_truncates_with_marker_head_and_tail(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KODE_MAX_TOOL_RESULT_CHARS", "1000")
        text = "CABEZA" + ("a" * 5000) + "COLA"
        out = guard_tool_output(text, "file_read", data_dir=tmp_path)
        assert "resultado truncado" in out
        assert "CABEZA" in out
        assert "COLA" in out
        assert len(out) < len(text)

    def test_spill_contains_full_original(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KODE_MAX_TOOL_RESULT_CHARS", "1000")
        text = "ñ" * 20000
        out = guard_tool_output(text, "file_read", session_id="tui_abc", data_dir=tmp_path)
        spills = list((tmp_path / "tool-results" / "tui_abc").glob("file_read-*.txt"))
        assert len(spills) == 1
        assert spills[0].read_text(encoding="utf-8") == text
        assert str(spills[0]) in out  # la ruta viaja al modelo

    def test_tool_name_is_sanitized(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KODE_MAX_TOOL_RESULT_CHARS", "10")
        guard_tool_output("x" * 100, "../../evil name", data_dir=tmp_path)
        files = list((tmp_path / "tool-results").rglob("*.txt"))
        assert len(files) == 1
        assert ".." not in files[0].name
        assert files[0].parent == tmp_path / "tool-results" / "nosession"

    def test_old_spills_are_purged(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KODE_MAX_TOOL_RESULT_CHARS", "10")
        directory = tmp_path / "tool-results" / "nosession"
        directory.mkdir(parents=True)
        old = directory / "old.txt"
        old.write_text("viejo")
        ancient = 1_000_000_000  # 2001
        os.utime(old, (ancient, ancient))
        guard_tool_output("y" * 100, "bash", data_dir=tmp_path)
        assert not old.exists()

    def test_spill_is_private(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KODE_MAX_TOOL_RESULT_CHARS", "10")
        guard_tool_output("z" * 100, "bash", data_dir=tmp_path)
        spill = next((tmp_path / "tool-results").rglob("*.txt"))
        assert (spill.stat().st_mode & 0o777) == 0o600


class TestConfig:
    def test_invalid_env_falls_back(self, monkeypatch):
        monkeypatch.setenv("KODE_MAX_TOOL_RESULT_CHARS", "no-numero")
        assert max_chars() == DEFAULT_MAX_CHARS

    def test_zero_env_falls_back(self, monkeypatch):
        monkeypatch.setenv("KODE_MAX_TOOL_RESULT_CHARS", "0")
        assert max_chars() == DEFAULT_MAX_CHARS
