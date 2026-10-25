"""Contrato del ledger del orquestador (F1).

El ledger es el estado compartido entre instancias frescas: ficheros del
workspace, registro append-only (record.jsonl), lista de tareas y SHA base.
Las escrituras deben ser atómicas: un fallo a mitad no puede dejar el
fichero de estado corrupto ni a medias.
"""

from __future__ import annotations

import json

import pytest

from bytia_kode.orchestrator.ledger import Ledger


def make_ledger(tmp_path) -> Ledger:
    return Ledger(tmp_path / "ws")


class TestWorkspace:
    def test_creates_workspace_dir(self, tmp_path):
        led = make_ledger(tmp_path)
        assert led.root.is_dir()


class TestTextFiles:
    def test_write_then_read(self, tmp_path):
        led = make_ledger(tmp_path)
        led.write_text("notes.md", "hola")
        assert led.read_text("notes.md") == "hola"

    def test_read_missing_returns_empty(self, tmp_path):
        led = make_ledger(tmp_path)
        assert led.read_text("nope.md") == ""

    def test_write_replaces_content(self, tmp_path):
        led = make_ledger(tmp_path)
        led.write_text("notes.md", "uno")
        led.write_text("notes.md", "dos")
        assert led.read_text("notes.md") == "dos"

    def test_write_leaves_no_tmp_file(self, tmp_path):
        led = make_ledger(tmp_path)
        led.write_text("notes.md", "x")
        assert list(led.root.glob("*.tmp")) == []

    def test_failed_replace_preserves_previous_content(self, tmp_path, monkeypatch):
        led = make_ledger(tmp_path)
        led.write_text("notes.md", "bueno")

        def boom(*args, **kwargs):
            raise OSError("fallo simulado")

        monkeypatch.setattr("bytia_kode.orchestrator.ledger.os.replace", boom)
        with pytest.raises(OSError):
            led.write_text("notes.md", "malo")

        assert (led.root / "notes.md").read_text(encoding="utf-8") == "bueno"
        assert list(led.root.glob("*.tmp")) == []


class TestRecord:
    def test_append_and_read(self, tmp_path):
        led = make_ledger(tmp_path)
        led.append_record({"role": "plan", "tokens": 10})
        led.append_record({"role": "worker", "tokens": 20})

        entries = led.record_entries()

        assert len(entries) == 2
        assert entries[0]["role"] == "plan"
        assert entries[1]["tokens"] == 20

    def test_record_is_jsonl_on_disk(self, tmp_path):
        led = make_ledger(tmp_path)
        led.append_record({"a": 1})

        line = (led.root / "record.jsonl").read_text(encoding="utf-8").strip()

        assert json.loads(line) == {"a": 1}

    def test_empty_record_reads_empty(self, tmp_path):
        assert make_ledger(tmp_path).record_entries() == []


class TestTasks:
    def test_tasks_roundtrip(self, tmp_path):
        led = make_ledger(tmp_path)
        tasks = [{"id": 1, "text": "hacer", "status": "pending"}]

        led.write_tasks(tasks)

        assert led.read_tasks() == tasks

    def test_missing_tasks_reads_empty_list(self, tmp_path):
        assert make_ledger(tmp_path).read_tasks() == []


class TestBaseSha:
    def test_base_sha_roundtrip(self, tmp_path):
        led = make_ledger(tmp_path)
        led.set_base_sha("abc123")
        assert led.get_base_sha() == "abc123"

    def test_missing_base_sha_returns_none(self, tmp_path):
        assert make_ledger(tmp_path).get_base_sha() is None
