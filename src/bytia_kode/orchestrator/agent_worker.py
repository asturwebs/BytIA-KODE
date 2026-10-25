"""Worker agéntico: instancia `Agent` de KODE como provider del runner (F2/T8)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from bytia_kode.orchestrator.jail import worker_jail
from bytia_kode.orchestrator.runner import Reply


class AgentWorker:
    """Provider síncrono del runner que ejecuta un `Agent` real confinado."""

    def __init__(
        self,
        *,
        config,
        scratch: Path,
        provider: str = "local",
        max_iter: int = 12,
        agent_factory=None,
    ):
        if agent_factory is None:
            from bytia_kode.agent import Agent  # lazy: importa config/registry

            agent_factory = Agent
        self.config = config
        self.scratch = Path(scratch)
        self.provider = provider
        self.max_iter = max_iter
        self._agent_factory = agent_factory

    def __call__(self, role: str, prompt: str) -> Reply:
        # El Agent siembra el jail global en __init__: se crea ANTES de
        # entrar en el jail del worker para que su siembra no lo pise.
        agent = self._agent_factory(self.config)
        agent.max_iterations = self.max_iter
        agent.providers.pin(self.provider)
        with worker_jail(self.scratch):
            text = asyncio.run(self._collect(agent, prompt))
        return Reply(
            text=text,
            tokens=agent.estimate_tokens(prompt) + agent.estimate_tokens(text),
        )

    async def _collect(self, agent, prompt: str) -> str:
        chunks: list[str] = []
        try:
            async for chunk in agent.chat(prompt, provider=self.provider):
                if isinstance(chunk, str):
                    chunks.append(chunk)
                elif isinstance(chunk, tuple) and chunk and chunk[0] == "text":
                    chunks.append(chunk[1])
        finally:
            await agent.close()
        return "".join(chunks).strip()
