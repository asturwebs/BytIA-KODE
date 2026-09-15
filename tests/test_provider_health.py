"""Tests for ProviderManager health tracking and get_healthy()."""
import pytest
from unittest.mock import MagicMock

from bytia_kode.providers.manager import ProviderManager


@pytest.fixture
def manager():
    cfg = MagicMock()
    cfg.base_url = "http://primary:8080/v1"
    cfg.api_key = "key1"
    cfg.model = "test-model"
    cfg.fallback_url = "http://fallback:8080/v1"
    cfg.fallback_key = "key2"
    cfg.fallback_model = "fallback-model"
    cfg.local_url = "http://local:11434/v1"
    cfg.local_model = "local-model"
    return ProviderManager(cfg)


class TestProviderManagerHealth:
    def test_get_healthy_returns_preferred_when_closed(self, manager):
        client, name = manager.get_healthy("primary")
        assert name == "primary"

    def test_get_healthy_skips_open_circuit(self, manager):
        manager._circuits["primary"].record_failure()
        manager._circuits["primary"].record_failure()
        manager._circuits["primary"].record_failure()
        assert manager._circuits["primary"].state == "open"
        client, name = manager.get_healthy("primary")
        # Orden local-first: el siguiente vivo tras primary es unsloth
        assert name == "unsloth"

    def test_get_healthy_all_open_returns_preferred(self, manager):
        for cb in manager._circuits.values():
            for _ in range(3):
                cb.record_failure()
        client, name = manager.get_healthy("primary")
        assert name == "primary"

    def test_report_success_resets_circuit(self, manager):
        manager._circuits["primary"].record_failure()
        manager._circuits["primary"].record_failure()
        assert manager._circuits["primary"].state == "closed"
        manager._circuits["primary"].record_failure()
        assert manager._circuits["primary"].state == "open"
        manager._circuits["primary"]._state = manager._circuits["primary"].HALF_OPEN
        assert manager._circuits["primary"].state == "half_open"
        manager.report_success("primary")
        assert manager._circuits["primary"].state == "closed"

    def test_report_failure_increments(self, manager):
        assert manager._circuits["primary"].state == "closed"
        manager.report_failure("primary")
        manager.report_failure("primary")
        assert manager._circuits["primary"].state == "closed"
        manager.report_failure("primary")
        assert manager._circuits["primary"].state == "open"

    def test_list_available_excludes_open(self, manager):
        for _ in range(3):
            manager._circuits["primary"].record_failure()
        assert manager._circuits["primary"].state == "open"
        available = manager.list_available()
        assert "primary" not in available
        assert "fallback" in available

    def test_get_status_returns_all_circuits(self, manager):
        status = manager.get_status()
        assert "primary" in status
        assert status["primary"]["state"] == "closed"
        assert status["primary"]["failures"] == 0


class TestUnslothSlot:
    def test_unsloth_slot_registered_when_configured(self, manager):
        # MagicMock: unsloth_url/unsloth_key son truthy por defecto → slot activo
        assert manager.unsloth is not None
        assert manager.get("unsloth") is manager.unsloth
        assert manager._priority_order == ["primary", "unsloth", "local", "fallback", "deepseek"]
        assert "unsloth" in manager.list_available()

    def test_unsloth_slot_absent_without_key(self):
        cfg = MagicMock()
        cfg.base_url = "http://primary:8080/v1"
        cfg.fallback_url = ""
        cfg.fallback_key = ""
        cfg.local_url = ""
        cfg.unsloth_url = "http://localhost:8888/v1"
        cfg.unsloth_key = ""  # sin key → slot no se crea
        mgr = ProviderManager(cfg)
        assert mgr.unsloth is None
        assert "unsloth" not in mgr.list_available()
        with pytest.raises(ValueError, match="No unsloth provider"):
            mgr.get("unsloth")

    def test_local_first_failover_order(self, manager):
        # Locales antes que nube: router → unsloth → ollama → z.ai → deepseek
        assert manager._priority_order == ["primary", "unsloth", "local", "fallback", "deepseek"]


class TestStartupProbing:
    @pytest.mark.asyncio
    async def test_dead_locals_open_circuit_at_startup(self):
        cfg = MagicMock()
        cfg.base_url = "http://127.0.0.1:1/v1"  # puerto iralcanzable
        cfg.model = "m"
        cfg.fallback_url = "http://127.0.0.1:2/v1"
        cfg.fallback_model = "f"
        cfg.local_url = "http://127.0.0.1:3/v1"
        cfg.local_model = "l"
        cfg.unsloth_url = "http://127.0.0.1:4/v1"
        cfg.unsloth_model = "u"
        mgr = ProviderManager(cfg)
        detected = await mgr.auto_detect_model()
        assert detected is False
        # Todos los locales sonados caen; la nube no se sondea (círculos cerrados)
        for name in ("primary", "unsloth", "local"):
            assert mgr._circuits[name].state == "open"
        assert mgr._circuits["fallback"].state == "closed"

    @pytest.mark.asyncio
    async def test_alive_locals_stay_closed(self):
        cfg = MagicMock()
        mgr = ProviderManager(cfg)
        for name in ("primary", "unsloth", "local"):
            async def fake_list_models():
                return ["some-model"]
            getattr(mgr, f"_{name}").list_models = fake_list_models
        detected = await mgr.auto_detect_model()
        assert detected is True
        for name in ("primary", "unsloth", "local"):
            assert mgr._circuits[name].state == "closed"
