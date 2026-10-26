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
    (root / "conftest.py").write_text("# base\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n\n'
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
        encoding="utf-8",
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
        assert set(scratch.test_paths()) == {"tests/test_app.py", "conftest.py"}


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
        assert (
            scratch.path / "conftest.py"
        ).read_text(encoding="utf-8") == "# base\n"
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


class TestReviewFixes:
    def test_restore_after_checkpoint_with_modified_test(self, scratch, repo):
        root, _ = repo
        base_content = (root / "tests" / "test_app.py").read_text(encoding="utf-8")
        (scratch.path / "tests" / "test_app.py").write_text(
            "def test_hack():\n    pass\n", encoding="utf-8"
        )
        scratch.checkpoint("checkpoint")

        scratch.restore_tests()

        assert (
            scratch.path / "tests" / "test_app.py"
        ).read_text(encoding="utf-8") == base_content

    def test_restore_after_checkpoint_with_new_test(self, scratch):
        (scratch.path / "tests" / "test_new.py").write_text(
            "def test_nueva():\n    pass\n", encoding="utf-8"
        )
        scratch.checkpoint("checkpoint")

        scratch.restore_tests()

        assert not (scratch.path / "tests" / "test_new.py").exists()

    def test_untracked_test_outside_tests_dir_is_removed(self, scratch):
        (scratch.path / "test_regression.py").write_text(
            "def test_x():\n    pass\n", encoding="utf-8"
        )
        (scratch.path / "src" / "tests").mkdir()
        (scratch.path / "src" / "tests" / "test_new.py").write_text(
            "def test_y():\n    pass\n", encoding="utf-8"
        )

        scratch.restore_tests()

        assert not (scratch.path / "test_regression.py").exists()
        assert not (scratch.path / "src" / "tests" / "test_new.py").exists()

    def test_pyproject_pytest_section_is_restored(self, scratch, repo):
        root, _ = repo
        base_pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        target = scratch.path / "pyproject.toml"
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                'testpaths = ["tests"]',
                'testpaths = ["tests"]\naddopts = "--deselect tests/test_app.py::test_x"',
            ),
            encoding="utf-8",
        )

        scratch.restore_tests()

        restored = target.read_text(encoding="utf-8")
        assert "addopts" not in restored
        assert '[project]\nname = "x"' in restored
        assert restored == base_pyproject

    def test_rename_from_test_is_cleaned(self, scratch, repo):
        root, _ = repo
        base_conftest = (root / "conftest.py").read_text(encoding="utf-8")
        git("mv", "conftest.py", "helpers.py", cwd=scratch.path)

        scratch.restore_tests()

        assert not (scratch.path / "helpers.py").exists()
        assert (
            scratch.path / "conftest.py"
        ).read_text(encoding="utf-8") == base_conftest

    def test_rename_from_test_with_rewrite_is_fail_closed(self, scratch, repo):
        root, _ = repo
        base_conftest = (root / "conftest.py").read_text(encoding="utf-8")
        git("mv", "conftest.py", "helpers.py", cwd=scratch.path)
        (scratch.path / "helpers.py").write_text(
            "# conftest TAMPERADO\n", encoding="utf-8"
        )
        git("add", "-A", cwd=scratch.path)

        with pytest.raises(Exception):
            scratch.restore_tests()

        assert (
            scratch.path / "conftest.py"
        ).read_text(encoding="utf-8") == base_conftest

    def test_file_named_test_is_not_deleted(self, scratch):
        (scratch.path / "test").write_text("legitimo\n", encoding="utf-8")

        scratch.restore_tests()

        assert (scratch.path / "test").exists()

    def test_context_manager_tears_down(self, tmp_path, repo):
        root, sha = repo
        with Scratch(repo=root, base_sha=sha, root=tmp_path / "ws2") as scratch:
            path = scratch.path
            assert path.is_dir()
        assert not path.exists()

    def test_create_rejects_stale_dir(self, tmp_path, repo):
        root, sha = repo
        stale = tmp_path / "ws3"
        (stale / "scratch").mkdir(parents=True)
        instance = Scratch(repo=root, base_sha=sha, root=stale)

        with pytest.raises(Exception):
            instance.create()

    def test_teardown_removes_stale_dir(self, tmp_path, repo):
        root, sha = repo
        stale = tmp_path / "ws4"
        (stale / "scratch").mkdir(parents=True)
        instance = Scratch(repo=root, base_sha=sha, root=stale)

        instance.teardown()

        assert not (stale / "scratch").exists()

    def test_diff_binary_includes_content(self, scratch):
        (scratch.path / "src" / "fixture.bin").write_bytes(b"\x00\x01\x02")

        patch = scratch.diff()

        assert "GIT binary patch" in patch

    def test_pycache_is_not_a_test_path(self):
        assert is_test_path("tests/__pycache__/test_x.cpython-313.pyc") is False

    def test_diff_excludes_pycache(self, scratch):
        cache = scratch.path / "tests" / "__pycache__"
        cache.mkdir()
        (cache / "test_x.cpython-313.pyc").write_bytes(b"\x00\x01")

        patch = scratch.diff()

        assert "__pycache__" not in patch

    def test_touched_test_paths_ignores_pycache(self, scratch):
        cache = scratch.path / "tests" / "__pycache__"
        cache.mkdir()
        (cache / "test_x.cpython-313.pyc").write_bytes(b"\x00\x01")

        assert scratch.touched_test_paths() == []

    def test_diff_excludes_worker_backups(self, scratch):
        # E2E real: el worker (Agent de KODE) creó calc.py.backup-*.
        (scratch.path / "src" / "calc.py.backup-20261025").write_text(
            "viejo\n", encoding="utf-8"
        )

        assert ".backup-" not in scratch.diff()

    def test_restore_removes_ignored_new_test(self, scratch):
        # H1: el worker añade el test al .gitignore para que clean -fd no lo borre.
        (scratch.path / ".gitignore").write_text(
            "tests/test_evil.py\n", encoding="utf-8"
        )
        (scratch.path / "tests" / "test_evil.py").write_text(
            "def test_evil():\n    pass\n", encoding="utf-8"
        )

        assert "tests/test_evil.py" in scratch.touched_test_paths()
        scratch.restore_tests()

        assert not (scratch.path / "tests" / "test_evil.py").exists()

    def test_checkpoint_with_only_artifacts_is_noop(self, scratch, repo):
        _, sha = repo
        cache = scratch.path / "tests" / "__pycache__"
        cache.mkdir()
        (cache / "x.pyc").write_bytes(b"\x00")

        assert scratch.checkpoint("solo artefactos") == sha
