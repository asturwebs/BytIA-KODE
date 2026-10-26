"""Providers del orquestador (F2/T9).

``RoleProvider`` rutea el ``provider(role, prompt)`` del runner: worker →
AgentWorker (agéntico, con tools), resto → TextProvider (manager por texto).
Un fallo del provider (circuit abierto, timeout) propaga al runner, que lo
convierte en estado ``infra``.
"""

from __future__ import annotations

import asyncio

from bytia_kode.orchestrator.runner import Reply
from bytia_kode.providers.client import Message


class TextProvider:
    def __init__(
        self, *, client_factory, max_tokens: int = 8192, temperature: float = 0.3
    ):
        self.client_factory = client_factory
        self.max_tokens = max_tokens
        self.temperature = temperature

    def __call__(self, role: str, prompt: str) -> Reply:
        return asyncio.run(self._request(prompt))

    async def _request(self, prompt: str) -> Reply:
        client = self.client_factory()
        try:
            response = await client.chat(
                [Message(role="user", content=prompt)],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
        finally:
            await client.close()
        text = response.content or ""
        usage = response.usage or {}
        total = usage.get("total_tokens") if isinstance(usage, dict) else None
        tokens = int(total) if total else (len(prompt) // 4 + len(text) // 4)
        return Reply(text=text, tokens=tokens)


class RoleProvider:
    def __init__(self, *, text, worker):
        self.text = text
        self.worker = worker

    def __call__(self, role: str, prompt: str) -> Reply:
        if role == "worker":
            return self.worker(role, prompt)
        return self.text(role, prompt)
