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
        assert name == "fallback"

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
