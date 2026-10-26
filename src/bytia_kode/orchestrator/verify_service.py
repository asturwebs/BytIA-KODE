"""Verificación real de un repo contra el baseline del HEAD (F2, pieza práctica)."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from bytia_kode.orchestrator.verify import Verifier, VerifyResult
from bytia_kode.orchestrator.workspace import Scratch


class VerifyServiceError(RuntimeError):
    pass


@dataclass
class VerifyOutcome:
    ok: bool
    baseline_failures: int
    current: VerifyResult


class VerifyService:
    def __init__(
        self,
        *,
        repo: Path,
        verify_cmd: str | None = None,
        workspace_root: Path | None = None,
    ):
        self.repo = Path(repo)
        self.verify_cmd = verify_cmd
        self.workspace_root = Path(
            workspace_root
            or Path.home() / ".bytia-kode" / "workspaces" / f"verify-{int(time.time())}"
        )

    def _head(self) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise VerifyServiceError("no es un repo git")
        return result.stdout.strip()

    def run(self) -> VerifyOutcome:
        base_sha = self._head()
        verifier = Verifier(command=self.verify_cmd)
        scratch = Scratch(
            repo=self.repo, base_sha=base_sha, root=self.workspace_root
        )
        scratch.create()
        try:
            baseline = verifier.capture_baseline(scratch.path)
        finally:
            scratch.teardown()
        current = verifier.run(self.repo, baseline=baseline)
        return VerifyOutcome(
            ok=current.ok,
            baseline_failures=len(baseline),
            current=current,
        )
