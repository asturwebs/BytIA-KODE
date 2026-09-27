"""AST-20: el hook de hatchling estampa el commit en wheel/sdist (build time).

Verificado además contra hatchling real (1.32.4): wheel, sdist y wheel
construido desde sdist conservan la estampa pese al .gitignore, y el árbol
queda limpio tras el build — ver comentario del issue AST-20.
"""
import subprocess
from pathlib import Path

import hatch_build  # vive en la raíz del repo; el conftest lo pone en sys.path

_REPO_STAMP = "src/bytia_kode/_commit.txt"


def _repo_root(tmp_path, *, with_git: bool = True) -> Path:
    root = tmp_path / "repo"
    (root / "src" / "bytia_kode").mkdir(parents=True)
    if with_git:
        (root / ".git").mkdir()
    return root


def _git_says(monkeypatch, stdout: str, returncode: int = 0):
    monkeypatch.setattr(
        hatch_build.subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess([], returncode, stdout=stdout),
    )


def test_resolve_commit_reads_git_of_the_checkout(monkeypatch, tmp_path):
    root = _repo_root(tmp_path)
    _git_says(monkeypatch, "60bac33\n")
    assert hatch_build.resolve_commit(root) == "60bac33"


def test_resolve_commit_ignores_foreign_repo(monkeypatch, tmp_path):
    # Un sdist desempaquetado dentro de otro repo no debe estampar su hash
    root = _repo_root(tmp_path, with_git=False)
    _git_says(monkeypatch, "otro99\n")
    assert hatch_build.resolve_commit(root) is None


def test_resolve_commit_without_git_binary(monkeypatch, tmp_path):
    root = _repo_root(tmp_path)

    def _no_git(*args, **kwargs):
        raise FileNotFoundError("git no instalado")

    monkeypatch.setattr(hatch_build.subprocess, "run", _no_git)
    assert hatch_build.resolve_commit(root) is None


def test_stamp_build_writes_stamp_and_declares_artifact(monkeypatch, tmp_path):
    root = _repo_root(tmp_path)
    monkeypatch.setattr(hatch_build, "resolve_commit", lambda r: "60bac33")
    build_data = {"artifacts": []}
    hatch_build.stamp_build(root, build_data)
    assert (root / _REPO_STAMP).read_text(encoding="utf-8").strip() == "60bac33"
    assert _REPO_STAMP in build_data["artifacts"]


def test_stamp_build_declares_inherited_sdist_stamp(tmp_path):
    # Wheel construido desde un sdist: sin .git, pero la estampa viaja dentro
    root = _repo_root(tmp_path, with_git=False)
    hatch_build.write_stamp(root, "60bac33")
    build_data = {"artifacts": []}
    hatch_build.stamp_build(root, build_data)
    assert _REPO_STAMP in build_data["artifacts"]


def test_stamp_build_without_git_leaves_tree_untouched(tmp_path):
    root = _repo_root(tmp_path, with_git=False)
    build_data = {"artifacts": []}
    hatch_build.stamp_build(root, build_data)
    assert build_data["artifacts"] == []
    assert not (root / _REPO_STAMP).exists()


def test_clear_stamp_is_idempotent(tmp_path):
    root = _repo_root(tmp_path)
    hatch_build.write_stamp(root, "60bac33")
    hatch_build.clear_stamp(root)
    hatch_build.clear_stamp(root)
    assert not (root / _REPO_STAMP).exists()
