"""E2E real: /escalate sobre un repo con bug, usando el router local."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bytia_kode.config import AppConfig
from bytia_kode.orchestrator.agent_worker import AgentWorker
from bytia_kode.orchestrator.providers import RoleProvider, TextProvider
from bytia_kode.orchestrator.service import EscalationService
from bytia_kode.providers.client import ProviderClient

ROUTER = "http://localhost:8080/v1"
MODEL = "qwen38-160k"
REPO = Path("/tmp/kode-e2e-repo")
WORKSPACE = Path("/tmp/kode-e2e-ws")


def main() -> int:
    config = AppConfig()
    config.provider.base_url = ROUTER
    config.provider.model = MODEL
    config.provider.api_key = "dummy"

    def provider_factory(scratch: Path):
        text = TextProvider(
            client_factory=lambda: ProviderClient(ROUTER, "dummy", MODEL)
        )
        worker = AgentWorker(
            config=config, scratch=scratch, provider="primary", max_iter=12
        )
        return RoleProvider(text=text, worker=worker)

    service = EscalationService(
        config=config,
        repo=REPO,
        task=(
            "Corrige el bug de src/calc.py: la funcion add(a, b) debe devolver "
            "la suma de a y b, no la resta. No modifiques los tests."
        ),
        workspace_root=WORKSPACE,
        provider_factory=provider_factory,
        progress=lambda message: print(f"[progress] {message}", flush=True),
    )

    started = time.time()
    outcome = service.run()
    elapsed = time.time() - started
    print("=== RESULTADO ===")
    print(
        f"status={outcome.result.status} rounds={outcome.result.rounds} "
        f"tokens={outcome.result.tokens} segundos={elapsed:.1f}"
    )
    print(f"detail={outcome.result.detail}")
    print("=== PATCH ===")
    print(outcome.patch[:5000])
    return 0 if outcome.result.status == "done" else 1


if __name__ == "__main__":
    raise SystemExit(main())
