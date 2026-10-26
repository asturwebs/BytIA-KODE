"""Contrato de /init: descubrir y generar B-KODE.md (contexto del proyecto)."""

from __future__ import annotations

from bytia_kode.agent import (
    backup_bkode_file,
    find_bkode,
    resolve_bkode_imports,
)


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


class TestImports:
    def test_relative_import_is_expanded(self, tmp_path):
        (tmp_path / "extra.md").write_text("contenido importado", encoding="utf-8")

        expanded = resolve_bkode_imports("antes\n@extra.md\ndespues", tmp_path)

        assert "contenido importado" in expanded
        assert "@extra.md" not in expanded

    def test_import_inside_fence_is_ignored(self, tmp_path):
        (tmp_path / "extra.md").write_text("contenido importado", encoding="utf-8")
        content = "```\n@extra.md\n```"

        assert resolve_bkode_imports(content, tmp_path) == content

    def test_cycle_does_not_hang(self, tmp_path):
        (tmp_path / "a.md").write_text("A\n@b.md", encoding="utf-8")
        (tmp_path / "b.md").write_text("B\n@a.md", encoding="utf-8")

        expanded = resolve_bkode_imports("@a.md", tmp_path)

        assert "A" in expanded and "B" in expanded

    def test_missing_import_is_kept(self, tmp_path):
        content = "@no-existe.md"
        assert resolve_bkode_imports(content, tmp_path) == content


class TestBackup:
    def test_backup_copies_content(self, tmp_path):
        source = tmp_path / "repo" / "B-KODE.md"
        source.parent.mkdir()
        source.write_text("contenido original", encoding="utf-8")

        backup = backup_bkode_file(source, backups_dir=tmp_path / "backups")

        assert backup.is_file()
        assert backup.read_text(encoding="utf-8") == "contenido original"
        assert backup.parent == tmp_path / "backups"
        assert backup.name.startswith("B-KODE-repo-")
