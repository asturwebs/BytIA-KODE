"""Provider management - switch between providers at runtime."""
from __future__ import annotations

import json
import logging
import os

from bytia_kode.config import ProviderConfig
from bytia_kode.providers.circuit import CircuitBreaker
from bytia_kode.providers.client import ProviderClient

logger = logging.getLogger(__name__)


def _extra_body(name: str) -> dict:
    """Vendor-specific payload params per slot, JSON in {NAME}_EXTRA_BODY (e.g. FALLBACK_EXTRA_BODY).

    Permite pasar parámetros tipo reasoning_effort / thinking sin acoplar el cliente a un vendor.
    """
    raw = os.environ.get(f"{name}_EXTRA_BODY", "")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        logger.warning("%s_EXTRA_BODY no es JSON válido — ignorado", name)
        return {}


class ProviderManager:
    """Manages multiple provider clients with fallback + manual pinning."""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self._primary = ProviderClient(config.base_url, config.api_key, config.model, extra_body=_extra_body("PROVIDER"))
        self._fallback: ProviderClient | None = None
        self._deepseek: ProviderClient | None = None
        self._local: ProviderClient | None = None
        self._unsloth: ProviderClient | None = None

        if config.fallback_url and config.fallback_key:
            self._fallback = ProviderClient(config.fallback_url, config.fallback_key, config.fallback_model, extra_body=_extra_body("FALLBACK"))

        if config.deepseek_url and config.deepseek_key:
            self._deepseek = ProviderClient(config.deepseek_url, config.deepseek_key, config.deepseek_model, extra_body=_extra_body("DEEPSEEK"))

        if config.local_url:
            self._local = ProviderClient(
                config.local_url,
                "not-needed",
                config.local_model,
                extra_body=_extra_body("LOCAL"),
            )

        if config.unsloth_url and config.unsloth_key:
            self._unsloth = ProviderClient(config.unsloth_url, config.unsloth_key, config.unsloth_model, extra_body=_extra_body("UNSLOTH"))

        self._circuits: dict[str, CircuitBreaker] = {"primary": CircuitBreaker()}
        for name in ("fallback", "deepseek", "local", "unsloth"):
            if getattr(self, f"_{name}"):
                self._circuits[name] = CircuitBreaker()
        # Cadena AUTO (decisión Socio 15-sep): solo motores siempre-disponibles —
        # Unsloth Studio (bandeja, autostart) → Ollama (servicio) → nube (z.ai → deepseek).
        # El router llama.cpp (:8080) es BAJO DEMANDA: fuera del walk de failover,
        # solo se usa con pin manual (F3) — o como último recurso si TODO está caído.
        self._priority_order = [
            name
            for name in ("unsloth", "local", "fallback", "deepseek")
            if name in self._circuits
        ]

        self._pinned: str | None = None

    @property
    def pinned(self) -> str | None:
        return self._pinned

    def pin(self, provider: str | None) -> None:
        self._pinned = provider

    async def auto_detect_model(self) -> bool:
        """Probe tray/service engines at startup, resolve 'auto' models, open circuits of dead slots.

        Cadena auto del Socio (15-sep): unsloth + local son los motores de arranque.
        El router (:8080) NO se auto-despierta: se sondea SOLO su catálogo (GET
        /v1/models no carga modelo) para tener el nombre listo si el Socio lo pinea
        a mano — eso es la "demanda". La nube no se sondea: reacciona a la 1ª petición.
        Devuelve True si hay algún local usable en la cadena auto (unsloth o local).
        """
        models = await self._primary.list_models()
        if not models:
            logger.info("Router :8080 sin respuesta — quedará fuera hasta demanda manual")
        elif self._primary.model == "auto":
            loaded = await self._primary.detect_loaded_model()
            if loaded or models:
                self._primary.model = loaded or models[0]
                logger.info("Router accesible (sin despertar) — modelo para demanda manual: %s", self._primary.model)

        detected = False
        for name in ("unsloth", "local"):
            client: ProviderClient | None = getattr(self, f"_{name}")
            circuit = self._circuits.get(name)
            if not client or not circuit:
                continue
            models = await client.list_models()
            if models:
                detected = True
                if client.model == "auto":
                    client.model = models[0]
                    logger.info(
                        "%s model auto-detected: %s (%d disponibles)",
                        name, client.model, len(models),
                    )
            else:
                logger.warning("Slot '%s' sin respuesta — circuito abierto", name)
                circuit.force_open()
        return detected

    @property
    def primary(self) -> ProviderClient:
        return self._primary

    @property
    def fallback(self) -> ProviderClient | None:
        return self._fallback

    @property
    def deepseek(self) -> ProviderClient | None:
        return self._deepseek

    @property
    def local(self) -> ProviderClient | None:
        return self._local

    @property
    def unsloth(self) -> ProviderClient | None:
        return self._unsloth

    def get(self, name: str = "primary") -> ProviderClient:
        """Get provider by name: primary, fallback, deepseek, local."""
        match name:
            case "primary":
                return self._primary
            case "fallback":
                if not self._fallback:
                    raise ValueError("No fallback provider configured")
                return self._fallback
            case "deepseek":
                if not self._deepseek:
                    raise ValueError("No deepseek provider configured")
                return self._deepseek
            case "local":
                if not self._local:
                    raise ValueError("No local provider configured")
                return self._local
            case "unsloth":
                if not self._unsloth:
                    raise ValueError("No unsloth provider configured")
                return self._unsloth
            case _:
                raise ValueError(f"Unknown provider: {name}")

    async def close_all(self):
        await self._primary.close()
        if self._fallback:
            await self._fallback.close()
        if self._deepseek:
            await self._deepseek.close()
        if self._local:
            await self._local.close()
        if self._unsloth:
            await self._unsloth.close()

    def list_available(self) -> list[str]:
        """Return list of provider names with healthy circuits."""
        return [name for name in self._priority_order if self._circuits[name].is_available]

    def list_pinnable(self) -> list[str]:
        """Motores ofrecidos al pin manual (F3): cadena auto + router bajo demanda.

        list_available() alimenta el walk de failover y NO incluye 'primary'
        (el router no se despierta solo); el switch manual sí debe ofrecerlo.
        """
        nombres = list(self._priority_order)
        if "primary" in self._circuits:
            nombres.append("primary")
        return [name for name in nombres if self._circuits[name].is_available]

    def set_model(self, provider: str, model: str):
        """Update model for a provider at runtime."""
        client = self.get(provider)
        client.model = model

    def get_healthy(self, preferred: str = "primary") -> tuple[ProviderClient, str]:
        """Return (client, name) of first available provider.

        If pinned, always return pinned provider (sticky — no auto-fallback).
        When no pin, walks priority order from the top with circuit breaker.
        """
        if self._pinned:
            return self.get(self._pinned), self._pinned

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

    def get_context_limit(self, provider: str) -> int:
        """Return configured context limit for a provider. 0 = use default/router."""
        match provider:
            case "deepseek":
                return self.config.deepseek_max_context
            case _:
                return 0
