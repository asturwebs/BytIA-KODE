"""Scratch git-worktree del orquestador (F2/T6).

El worker edita un ``git worktree`` desechable. R3: sin worktree no hay
elegibilidad. R4: el context manager garantiza teardown también en error.
R6: ``git add -A`` antes de checkpoint y diff. R2: el restore de tests deja
status limpio **contra el SHA base** (no contra HEAD), cubre tests nuevos en
cualquier ruta y renames, y restaura la sección pytest del ``pyproject.toml``.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath

TEST_DIR_NAMES = {"tests", "test"}
TEST_FILES = {"conftest.py", "pytest.ini", "tox.ini", "noxfile.py"}
_PYTEST_SECTION = re.compile(
    r"(?ms)^\[tool\.pytest\.ini_options\].*?(?=^\[[^\]]+\]|\Z)"
)
# Artefactos que genera pytest/git y NO deben entrar en el patch ni contar
# como toque de tests (el verify corre pytest dentro del scratch).
_ARTIFACT_EXCLUDES = (
    ":(exclude)**/__pycache__/**",
    ":(exclude)**/*.pyc",
    ":(exclude)**/*.pyo",
    ":(exclude).pytest_cache/**",
    ":(exclude)**/*.backup-*",
    ":(exclude)**/*.bak",
    ":(exclude)**/*.orig",
    ":(exclude)**/*.rej",
)


class ScratchError(RuntimeError):
    pass


def is_test_path(path: str) -> bool:
    """Predicado ÚNICO compartido por detección y restore (R2.4)."""
    parsed = PurePosixPath(path)
    if "__pycache__" in parsed.parts or parsed.suffix in {".pyc", ".pyo"}:
        return False
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

    # -- context manager (R4 estructural) ---------------------------------
    def __enter__(self) -> "Scratch":
        self.create()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.teardown()
        return False

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

    def _is_worktree(self) -> bool:
        if not self.path.exists():
            return False
        result = self._git(
            "rev-parse", "--show-toplevel", cwd=self.path, check=False
        )
        return result.returncode == 0

    # -- ciclo de vida -----------------------------------------------------
    def create(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            if not self._is_worktree():
                raise ScratchError(
                    f"directorio rancio no-worktree en {self.path}"
                )
            return self.path
        self._git(
            "worktree", "add", "--detach", str(self.path), self.base_sha, cwd=self.repo
        )
        return self.path

    def teardown(self) -> None:
        if self._is_worktree():
            self._git(
                "worktree", "remove", "--force", str(self.path), cwd=self.repo, check=False
            )
        self._git("worktree", "prune", cwd=self.repo, check=False)
        if self.path.exists():
            shutil.rmtree(self.path)

    # -- estado ------------------------------------------------------------
    def head(self) -> str:
        return self._git("rev-parse", "HEAD").stdout.strip()

    def checkpoint(self, message: str) -> str:
        self._git("add", "-A", "--", ".", *_ARTIFACT_EXCLUDES)
        if self._git(
            "status", "--porcelain", "--", ".", *_ARTIFACT_EXCLUDES
        ).stdout.strip():
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
        self._git("add", "-A", "--", ".", *_ARTIFACT_EXCLUDES)
        return self._git(
            "diff", "--binary", self.base_sha, "--", ".", *_ARTIFACT_EXCLUDES
        ).stdout

    # -- tests -------------------------------------------------------------
    def _status_entries(self) -> list[tuple[str, str, str | None]]:
        """(código, path, origen) de `status --porcelain -z`, renames incluidos."""
        raw = self._git("status", "--porcelain", "-z").stdout
        parts = raw.split("\0")
        entries: list[tuple[str, str, str | None]] = []
        index = 0
        while index < len(parts):
            entry = parts[index]
            if not entry:
                index += 1
                continue
            code = entry[:2]
            path = entry[3:]
            if code.strip().startswith(("R", "C")):
                source = parts[index + 1] if index + 1 < len(parts) else ""
                entries.append((code, path, source))
                index += 2
            else:
                entries.append((code, path, None))
                index += 1
        return entries

    def _has_test_rename_evasion(self) -> bool:
        """Test borrado + fichero nuevo no-test = posible rename evasivo (fail-closed)."""
        entries = self._status_entries()
        deleted_test = any(
            "D" in code and is_test_path(path) for code, path, _ in entries
        )
        added_other = any(
            ("A" in code or "?" in code) and not is_test_path(path)
            for code, path, _ in entries
        )
        return deleted_test and added_other

    def _test_specs(self) -> list[str]:
        specs: set[str] = set()
        for path in self._git("ls-files").stdout.splitlines():
            if is_test_path(path):
                specs.add(path)
        for path in self.path.rglob("*"):
            if path.is_file() and ".git" not in path.parts:
                relative = path.relative_to(self.path).as_posix()
                if is_test_path(relative):
                    specs.add(relative)
        for _code, path, source in self._status_entries():
            if is_test_path(path) or (source and is_test_path(source)):
                specs.add(path)
                if source:
                    specs.add(source)
        return sorted(specs)

    def test_paths(self) -> list[str]:
        files = self._git("ls-files").stdout.splitlines()
        return [path for path in files if is_test_path(path)]

    def touched_test_paths(self) -> list[str]:
        """Rutas de test tocadas contra el SHA base (R2/C1), sin artefactos.

        `git diff` es ciego a untracked/ignored: se completa con un walk del
        worktree para tests que no existen en base (evasión `.gitignore`).
        """
        self._git("add", "-A", "--", ".", *_ARTIFACT_EXCLUDES)
        changed = set(
            self._git(
                "diff", "--name-only", self.base_sha, "--", ".", *_ARTIFACT_EXCLUDES
            ).stdout.splitlines()
        )
        base_tests = set(
            self._git("ls-tree", "-r", "--name-only", self.base_sha).stdout.splitlines()
        )
        for path in self.path.rglob("*"):
            if path.is_file() and ".git" not in path.parts:
                relative = path.relative_to(self.path).as_posix()
                if is_test_path(relative) and relative not in base_tests:
                    changed.add(relative)
        return [path for path in sorted(changed) if is_test_path(path)]

    def restore_tests(self) -> None:
        """Restaura tests desde el SHA base y deja status limpio (R2)."""
        evasion = self._has_test_rename_evasion()
        specs = self._test_specs()
        for spec in specs:
            self._git("reset", "-q", self.base_sha, "--", spec, check=False)
            self._git("checkout", "--", spec, check=False)
            self._git("clean", "-fdxq", "--", spec, check=False)
        self._restore_pyproject_pytest()
        if specs:
            remaining = self._git(
                "diff", "--name-only", self.base_sha, "--", *specs
            ).stdout.strip()
            if remaining:
                raise ScratchError(f"status no limpio tras restore: {remaining}")
        if evasion:
            raise ScratchError(
                "posible rename de test a fichero no-test con contenido reescrito"
            )

    def _restore_pyproject_pytest(self) -> None:
        """Restaura SOLO la sección [tool.pytest.ini_options] (R2.5/H3)."""
        target = self.path / "pyproject.toml"
        base = self._git("show", f"{self.base_sha}:pyproject.toml", check=False)
        if base.returncode != 0:
            return
        base_text = base.stdout
        current_text = target.read_text(encoding="utf-8") if target.exists() else ""
        base_section = _PYTEST_SECTION.search(base_text)
        current_section = _PYTEST_SECTION.search(current_text)
        if base_section:
            replacement = base_section.group(0)
            if current_section:
                new_text = (
                    current_text[: current_section.start()]
                    + replacement
                    + current_text[current_section.end() :]
                )
            else:
                new_text = current_text.rstrip() + "\n\n" + replacement
        elif current_section:
            new_text = (
                current_text[: current_section.start()]
                + current_text[current_section.end() :]
            )
        else:
            return
        target.write_text(new_text, encoding="utf-8")
