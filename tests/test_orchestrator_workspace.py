"""Contrato del scratch git-worktree (F2/T6).

El worker edita un worktree desechable; el repo del usuario nunca se toca.
R3: la elegibilidad exige worktree git (no `cp -r`). R4: teardown también en
error. R6: `git add -A` antes de checkpoint y diff. R2: el restore de tests
debe dejar status limpio, incluidos los tests NUEVOS.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from bytia_kode.orchestrator.workspace import Scratch, is_test_path


def git(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git("init", "-q", cwd=root)
    git("config", "user.email", "t@example.com", cwd=root)
    git("config", "user.name", "Test", cwd=root)
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_app.py").write_text(
        "def test_x():\n    assert True\n", encoding="utf-8"
    )
    git("add", "-A", cwd=root)
    git("commit", "-qm", "base", cwd=root)
    return root, git("rev-parse", "HEAD", cwd=root)


@pytest.fixture
def scratch(tmp_path, repo):
    root, sha = repo
    instance = Scratch(repo=root, base_sha=sha, root=tmp_path / "ws")
    instance.create()
    return instance


class TestCreateAndTeardown:
    def test_create_makes_worktree_at_base(self, scratch, repo):
        _, sha = repo
        assert scratch.path.is_dir()
        assert git("rev-parse", "HEAD", cwd=scratch.path) == sha

    def test_teardown_removes_worktree(self, scratch):
        scratch.teardown()
        assert not scratch.path.exists()

    def test_teardown_is_idempotent(self, scratch):
        scratch.teardown()
        scratch.teardown()


class TestCheckpointAndDiff:
    def test_checkpoint_commits_changes(self, scratch, repo):
        _, sha = repo
        (scratch.path / "src" / "app.py").write_text("x = 2\n", encoding="utf-8")

        head = scratch.checkpoint("ronda 1")

        assert head != sha
        assert git("log", "-1", "--format=%s", cwd=scratch.path) == "ronda 1"
        assert git("status", "--porcelain", cwd=scratch.path) == ""

    def test_checkpoint_without_changes_is_noop(self, scratch, repo):
        _, sha = repo
        head = scratch.checkpoint("sin cambios")
        assert head == sha

    def test_diff_includes_untracked_files(self, scratch):
        (scratch.path / "src" / "new.py").write_text("y = 3\n", encoding="utf-8")

        patch = scratch.diff()

        assert "new.py" in patch
        assert "+y = 3" in patch


class TestTestPaths:
    def test_predicate(self):
        assert is_test_path("tests/test_app.py") is True
        assert is_test_path("src/tests/test_x.py") is True
        assert is_test_path("conftest.py") is True
        assert is_test_path("pytest.ini") is True
        assert is_test_path("src/app.py") is False

    def test_lists_tracked_test_files(self, scratch):
        assert scratch.test_paths() == ["tests/test_app.py"]


class TestRestoreTests:
    def test_restores_modified_and_removes_new(self, scratch, repo):
        root, _ = repo
        base_content = (root / "tests" / "test_app.py").read_text(encoding="utf-8")
        (scratch.path / "tests" / "test_app.py").write_text(
            "def test_hack():\n    assert True\n", encoding="utf-8"
        )
        (scratch.path / "tests" / "test_new.py").write_text(
            "def test_nueva():\n    assert True\n", encoding="utf-8"
        )
        (scratch.path / "conftest.py").write_text("# hack\n", encoding="utf-8")

        scratch.restore_tests()

        assert not (scratch.path / "tests" / "test_new.py").exists()
        assert not (scratch.path / "conftest.py").exists()
        assert (
            scratch.path / "tests" / "test_app.py"
        ).read_text(encoding="utf-8") == base_content
        assert (
            git("status", "--porcelain", "--", "tests", "conftest.py", cwd=scratch.path)
            == ""
        )

    def test_removes_staged_new_test(self, scratch):
        (scratch.path / "tests" / "test_new.py").write_text(
            "def test_nueva():\n    assert True\n", encoding="utf-8"
        )
        git("add", "tests/test_new.py", cwd=scratch.path)

        scratch.restore_tests()

        assert not (scratch.path / "tests" / "test_new.py").exists()
        assert (
            git("status", "--porcelain", "--", "tests", cwd=scratch.path) == ""
        )
