"""Scratch git-worktree del orquestador (F2/T6).

El worker edita un ``git worktree`` desechable; el repo del usuario nunca se
toca. R3: sin worktree no hay elegibilidad. R4: teardown también en error.
R6: ``git add -A`` antes de checkpoint y diff. R2: el restore de tests deja
status limpio, incluidos los tests NUEVOS.
"""

from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath

TEST_DIR_NAMES = {"tests", "test"}
TEST_FILES = {"conftest.py", "pytest.ini", "tox.ini", "noxfile.py"}


class ScratchError(RuntimeError):
    pass


def is_test_path(path: str) -> bool:
    """Predicado ÚNICO compartido por detección y restore (R2.4)."""
    parsed = PurePosixPath(path)
    if parsed.name in TEST_FILES:
        return True
    if parsed.name.startswith("test_") and parsed.suffix == ".py":
        return True
    return any(part in TEST_DIR_NAMES for part in parsed.parts[:-1])


class Scratch:
    def __init__(self, *, repo: Path, base_sha: str, root: Path):
        self.repo = Path(repo)
        self.base_sha = base_sha
        self.root = Path(root)
        self.path = self.root / "scratch"

    # -- git ---------------------------------------------------------------
    def _git(self, *args: str, cwd: Path | None = None, check: bool = True):
        result = subprocess.run(
            ["git", *args],
            cwd=cwd or self.path,
            capture_output=True,
            text=True,
        )
        if check and result.returncode != 0:
            raise ScratchError(result.stderr.strip() or result.stdout.strip())
        return result

    # -- ciclo de vida -----------------------------------------------------
    def create(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            return self.path
        self._git(
            "worktree", "add", "--detach", str(self.path), self.base_sha, cwd=self.repo
        )
        return self.path

    def teardown(self) -> None:
        if self.path.exists():
            self._git(
                "worktree", "remove", "--force", str(self.path), cwd=self.repo, check=False
            )
        self._git("worktree", "prune", cwd=self.repo, check=False)

    # -- estado ------------------------------------------------------------
    def head(self) -> str:
        return self._git("rev-parse", "HEAD").stdout.strip()

    def checkpoint(self, message: str) -> str:
        self._git("add", "-A")
        if self._git("status", "--porcelain").stdout.strip():
            self._git(
                "-c",
                "user.name=bytia-orchestrator",
                "-c",
                "user.email=bytia@localhost",
                "commit",
                "-qm",
                message,
            )
        return self.head()

    def diff(self) -> str:
        self._git("add", "-A")
        return self._git("diff", self.base_sha).stdout

    # -- tests -------------------------------------------------------------
    def test_paths(self) -> list[str]:
        files = self._git("ls-files").stdout.splitlines()
        return [path for path in files if is_test_path(path)]

    def _pathspecs(self) -> list[str]:
        candidates = ["tests", "test", *sorted(TEST_FILES), *self.test_paths()]
        specs: list[str] = []
        for spec in dict.fromkeys(candidates):
            in_base = bool(
                self._git(
                    "ls-tree", "-r", "--name-only", self.base_sha, "--", spec
                ).stdout.strip()
            )
            if in_base or (self.path / spec).exists():
                specs.append(spec)
        return specs

    def restore_tests(self) -> None:
        """Restaura tests desde el SHA base y deja status limpio (R2)."""
        specs = self._pathspecs()
        if not specs:
            return
        for spec in specs:
            self._git("reset", "-q", self.base_sha, "--", spec, check=False)
            self._git("checkout", "--", spec, check=False)
            self._git("clean", "-fdq", "--", spec, check=False)
        remaining = self._git("status", "--porcelain", "--", *specs).stdout.strip()
        if remaining:
            raise ScratchError(f"status no limpio tras restore: {remaining}")
