"""Integración del servicio de escalación (F2/T10-T11).

Stack completo sobre un repo git temporal: worktree, baseline, runner,
verificación real con pytest, tamper-check, patch final y teardown.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from bytia_kode.config import EscalationConfig
from bytia_kode.orchestrator.runner import Reply
from bytia_kode.orchestrator.service import EscalationService

PLAN = "### PLAN\nhacer\n### TASKS\n- cambiar x\n"
IDEATION = "### NOTES\nenfoque\n### NEXT\ncambiar\n"
WORKER = "### NOTES\nhecho\n### NEXT\nnada\n### STATUS\nsolved\n"
MANAGE_DONE = "### STATUS\ndone\n### TASKS\n- cambiar (done)\n"


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


def make_config(tmp_path):
    return SimpleNamespace(
        escalation=EscalationConfig(
            enabled=True, max_rounds=2, max_tokens=100_000
        ),
        data_dir=tmp_path / "data",
        provider=SimpleNamespace(),
    )


def make_provider(worker_body):
    class Provider:
        def __call__(self, role, prompt):
            if role == "primary_plan":
                return Reply(PLAN, 10)
            if role == "ideation":
                return Reply(IDEATION, 10)
            if role == "worker":
                worker_body()
                return Reply(WORKER, 10)
            if role == "primary_manage":
                return Reply(MANAGE_DONE, 10)
            raise AssertionError(f"rol inesperado: {role}")

    return Provider()


def test_happy_path_produces_patch_and_tears_down(tmp_path, repo):
    def change(scratch: "Path"):
        (scratch / "src" / "app.py").write_text("x = 2\n", encoding="utf-8")

    service = EscalationService(
        config=make_config(tmp_path),
        repo=repo,
        task="cambia x a 2",
        workspace_root=tmp_path / "ws",
        provider_factory=lambda scratch: make_provider(lambda: change(scratch)),
    )

    outcome = service.run()

    assert outcome.result.status == "done", outcome.result.detail
    assert "+x = 2" in outcome.patch
    assert not (tmp_path / "ws" / "scratch").exists()


def test_disabled_returns_ineligible(tmp_path, repo):
    cfg = make_config(tmp_path)
    cfg.escalation = EscalationConfig(enabled=False)
    service = EscalationService(
        config=cfg, repo=repo, task="x", workspace_root=tmp_path / "ws3"
    )

    outcome = service.run()

    assert outcome.result.status == "ineligible"
    assert "disabled" in outcome.result.detail


def test_tamper_is_invalidated_and_aborts(tmp_path, repo):
    def tamper(scratch: "Path"):
        (scratch / "tests" / "test_app.py").write_text(
            "def test_ok():\n    assert False\n", encoding="utf-8"
        )

    service = EscalationService(
        config=make_config(tmp_path),
        repo=repo,
        task="rompe los tests",
        workspace_root=tmp_path / "ws2",
        provider_factory=lambda scratch: make_provider(lambda: tamper(scratch)),
    )

    outcome = service.run()

    assert outcome.result.status == "protocol"
    assert "test-tamper" in outcome.result.detail
