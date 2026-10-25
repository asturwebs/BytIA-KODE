"""Servicio de escalación: stack completo + patch final (F2/T10-T11)."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from bytia_kode.orchestrator.ledger import Ledger
from bytia_kode.orchestrator.runner import Runner, RunnerConfig, RunResult, Verdict
from bytia_kode.orchestrator.specs import CODE_REPO
from bytia_kode.orchestrator.verify import Verifier
from bytia_kode.orchestrator.workspace import Scratch


@dataclass
class EscalationOutcome:
    result: RunResult
    patch: str
    workspace: Path


class EscalationService:
    """Ejecuta el ciclo completo sobre un worktree del repo objetivo."""

    def __init__(
        self,
        *,
        config,
        repo: Path,
        task: str,
        workspace_root: Path | None = None,
        base_sha: str | None = None,
        verify_cmd: str | None = None,
        manager_provider: str | None = None,
        worker_provider: str | None = None,
        provider_factory=None,
        max_iter: int | None = None,
        progress=None,
    ):
        self.config = config
        self.repo = Path(repo)
        self.task = task
        escalation = config.escalation
        self.workspace_root = Path(
            workspace_root
            or config.data_dir / "workspaces" / f"esc-{int(time.time())}"
        )
        self.base_sha = base_sha or self._repo_head()
        self.verify_cmd = verify_cmd
        self.manager_provider = manager_provider or escalation.manager_provider
        self.worker_provider = worker_provider or escalation.worker_provider
        self.max_iter = max_iter or escalation.worker_max_iter
        self.provider_factory = provider_factory
        self.progress = progress or (lambda message: None)

    # -- helpers -----------------------------------------------------------
    def _repo_head(self) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def _preflight(self) -> str | None:
        if not (self.repo / ".git").exists():
            return "ineligible: not-a-git-repo"
        return None

    def _default_provider(self, scratch_path: Path):
        from bytia_kode.orchestrator.agent_worker import AgentWorker
        from bytia_kode.orchestrator.providers import RoleProvider, TextProvider
        from bytia_kode.providers.manager import ProviderManager

        text = TextProvider(
            client_factory=lambda: ProviderManager(self.config.provider).get(
                self.manager_provider
            )
        )
        worker = AgentWorker(
            config=self.config,
            scratch=scratch_path,
            provider=self.worker_provider,
            max_iter=self.max_iter,
        )
        return RoleProvider(text=text, worker=worker)

    # -- ejecución ---------------------------------------------------------
    def run(self) -> EscalationOutcome:
        scratch = Scratch(
            repo=self.repo, base_sha=self.base_sha, root=self.workspace_root
        )
        scratch.create()
        try:
            self.progress("scratch listo")
            verifier = Verifier(command=self.verify_cmd)
            baseline = verifier.capture_baseline(scratch.path)
            self.progress(f"baseline: {len(baseline)} fallos preexistentes")

            provider = (self.provider_factory or self._default_provider)(scratch.path)

            def verify() -> Verdict:
                outcome = verifier.run(scratch.path, baseline=baseline)
                detail = outcome.error or f"{outcome.passed} passed · {outcome.failed} failed"
                if outcome.new_failures:
                    detail += " · nuevos: " + ", ".join(outcome.new_failures)
                return Verdict(ok=outcome.ok, detail=detail)

            runner = Runner(
                ledger=Ledger(self.workspace_root),
                spec=CODE_REPO,
                provider=provider,
                verifier=verify,
                config=RunnerConfig.from_escalation(self.config.escalation),
                tamper_check=lambda: bool(scratch.touched_test_paths()),
                restore_tests=scratch.restore_tests,
                preflight=self._preflight,
                base_sha=self.base_sha,
            )
            result = runner.run(self.task)
            self.progress(f"resultado: {result.status}")
            patch = scratch.diff()
            return EscalationOutcome(
                result=result, patch=patch, workspace=self.workspace_root
            )
        finally:
            scratch.teardown()
