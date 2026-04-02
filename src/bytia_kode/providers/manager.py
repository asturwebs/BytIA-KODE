"""Provider management - switch between providers at runtime."""
from __future__ import annotations

from bytia_kode.config import ProviderConfig
from bytia_kode.providers.client import ProviderClient


class ProviderManager:
    """Manages multiple provider clients with fallback."""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self._primary = ProviderClient(config.base_url, config.api_key, config.model)
        self._fallback: ProviderClient | None = None
        self._local: ProviderClient | None = None

        if config.fallback_url and config.fallback_key:
            self._fallback = ProviderClient(config.fallback_url, config.fallback_key, config.fallback_model)

        if config.local_url:
            self._local = ProviderClient(
                config.local_url,
                "not-needed",  # local models usually don't need keys
                config.local_model,
            )

    @property
    def primary(self) -> ProviderClient:
        return self._primary

    @property
    def fallback(self) -> ProviderClient | None:
        return self._fallback

    @property
    def local(self) -> ProviderClient | None:
        return self._local

    def get(self, name: str = "primary") -> ProviderClient:
        """Get provider by name: primary, fallback, local."""
        match name:
            case "primary":
                return self._primary
            case "fallback":
                if not self._fallback:
                    raise ValueError("No fallback provider configured")
                return self._fallback
            case "local":
                if not self._local:
                    raise ValueError("No local provider configured")
                return self._local
            case _:
                raise ValueError(f"Unknown provider: {name}")

    async def close_all(self):
        await self._primary.close()
        if self._fallback:
            await self._fallback.close()
        if self._local:
            await self._local.close()
