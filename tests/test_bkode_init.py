"""Contrato de /init: descubrir y generar B-KODE.md (contexto del proyecto)."""

from __future__ import annotations

from bytia_kode.agent import find_bkode


class TestFindBkode:
    def test_none_when_missing(self, tmp_path):
        assert find_bkode(tmp_path) is None

    def test_finds_in_start_dir(self, tmp_path):
        target = tmp_path / "B-KODE.md"
        target.write_text("x", encoding="utf-8")

        assert find_bkode(tmp_path) == target.resolve()

    def test_walks_up(self, tmp_path):
        target = tmp_path / "B-KODE.md"
        target.write_text("x", encoding="utf-8")
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)

        assert find_bkode(nested) == target.resolve()
