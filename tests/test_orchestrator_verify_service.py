"""Contrato de /verify: suite real del árbol de trabajo vs baseline del HEAD.

Es la pieza práctica de F2 sin orquestación: ¿el estado actual del repo
introduce fallos NUEVOS respecto al commit en el que empezaste? El baseline
se corre en un worktree desechable del HEAD; el estado actual, en tu repo.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from bytia_kode.orchestrator.verify_service import VerifyService, VerifyServiceError


def git(*args: str, cwd) -> None:
    subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )


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
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n\n'
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
        encoding="utf-8",
    )
    git("add", "-A", cwd=root)
    git("commit", "-qm", "base", cwd=root)
    return root


class TestVerifyService:
    def test_clean_repo_is_ok(self, tmp_path, repo):
        outcome = VerifyService(
            repo=repo, workspace_root=tmp_path / "ws"
        ).run()

        assert outcome.ok is True
        assert outcome.baseline_failures == 0
        assert outcome.current.passed >= 1

    def test_new_failure_in_working_tree_is_not_ok(self, tmp_path, repo):
        (repo / "tests" / "test_new_bad.py").write_text(
            "def test_bad():\n    assert False\n", encoding="utf-8"
        )

        outcome = VerifyService(
            repo=repo, workspace_root=tmp_path / "ws2"
        ).run()

        assert outcome.ok is False
        assert outcome.baseline_failures == 0
        assert len(outcome.current.new_failures) == 1

    def test_preexisting_failure_is_not_new(self, tmp_path, repo):
        (repo / "tests" / "test_bad.py").write_text(
            "def test_bad():\n    assert False\n", encoding="utf-8"
        )
        git("add", "-A", cwd=repo)
        git("commit", "-qm", "rojo conocido", cwd=repo)

        outcome = VerifyService(
            repo=repo, workspace_root=tmp_path / "ws3"
        ).run()

        assert outcome.baseline_failures == 1
        assert outcome.ok is True

    def test_not_a_repo_raises(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()

        with pytest.raises(VerifyServiceError):
            VerifyService(repo=plain, workspace_root=tmp_path / "ws4").run()

    def test_worktree_is_torn_down(self, tmp_path, repo):
        ws = tmp_path / "ws5"

        VerifyService(repo=repo, workspace_root=ws).run()

        assert not (ws / "scratch").exists()
