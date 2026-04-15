"""Provider management - switch between providers at runtime."""
from __future__ import annotations

import logging

from bytia_kode.config import ProviderConfig
from bytia_kode.providers.circuit import CircuitBreaker
from bytia_kode.providers.client import ProviderClient

logger = logging.getLogger(__name__)


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
                "not-needed",
                config.local_model,
            )

        self._circuits: dict[str, CircuitBreaker] = {"primary": CircuitBreaker()}
        if self._fallback:
            self._circuits["fallback"] = CircuitBreaker()
        if self._local:
            self._circuits["local"] = CircuitBreaker()
        self._priority_order = ["primary"]
        if self._fallback:
            self._priority_order.append("fallback")
        if self._local:
            self._priority_order.append("local")

    async def auto_detect_model(self) -> bool:
        """If primary model is 'auto', detect loaded model from router.

        Returns True if a model was detected, False otherwise.
        """
        if self._primary.model != "auto":
            return True
        loaded = await self._primary.detect_loaded_model()
        if loaded:
            self._primary.model = loaded
            logger.info("Auto-detected loaded model: %s", loaded)
            return True
        logger.warning("No model loaded on router")
        return False

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

    def list_available(self) -> list[str]:
        """Return list of provider names with healthy circuits."""
        return [name for name in self._priority_order if self._circuits[name].is_available]

    def set_model(self, provider: str, model: str):
        """Update model for a provider at runtime."""
        client = self.get(provider)
        client.model = model

    def get_healthy(self, preferred: str = "primary") -> tuple[ProviderClient, str]:
        """Return (client, name) of first available provider.

        Always walks priority order from the top — this lets circuit breakers
        naturally recover: a HALF_OPEN primary will be tried before fallback.
        Falls back to the requested provider as last resort if all circuits are OPEN.
        """
        for name in self._priority_order:
            cb = self._circuits.get(name)
            if cb and cb.is_available:
                return self.get(name), name

        logger.warning("All providers in OPEN state — using %s as last resort", preferred)
        return self.get(preferred), preferred

    def report_success(self, provider: str) -> None:
        cb = self._circuits.get(provider)
        if cb:
            cb.record_success()

    def report_failure(self, provider: str) -> None:
        cb = self._circuits.get(provider)
        if cb:
            cb.record_failure()
            if cb.state == "open":
                logger.warning("Circuit OPEN for provider '%s'", provider)

    def get_status(self) -> dict[str, dict]:
        return {
            name: {"state": cb.state, "failures": cb._failure_count}
            for name, cb in self._circuits.items()
        }
