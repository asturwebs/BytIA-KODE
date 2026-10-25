"""Claves KODE_ESCALATION_* (F1, §4.6).

Defaults cerrados: kill-switch off, manager y worker locales (C2: cloud
prohibido en repos de cliente), techo por worker 12 (C7) y presupuestos
duros. El entorno debe poder sobreescribirlos sin tocar código.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from bytia_kode.config import AppConfig


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    (tmp_path / "home").mkdir()
    for key in list(os.environ):
        if key.startswith("KODE_ESCALATION_"):
            monkeypatch.delenv(key, raising=False)

    def build() -> AppConfig:
        return AppConfig()

    return build


class TestEscalationDefaults:
    def test_kill_switch_is_off(self, isolated_config):
        assert isolated_config().escalation.enabled is False

    def test_manager_and_worker_are_local(self, isolated_config):
        escalation = isolated_config().escalation
        assert escalation.manager_provider == "local"
        assert escalation.worker_provider == "local"

    def test_worker_iteration_cap_is_12(self, isolated_config):
        assert isolated_config().escalation.worker_max_iter == 12

    def test_budgets_match_the_plan(self, isolated_config):
        escalation = isolated_config().escalation
        assert escalation.max_rounds == 4
        assert escalation.max_tasks == 8
        assert escalation.max_wallclock_min == 20
        assert escalation.max_tokens == 200_000

    def test_auto_trigger_is_off(self, isolated_config):
        escalation = isolated_config().escalation
        assert escalation.auto_trigger is False
        assert escalation.auto_after_iter == 6


class TestEscalationEnvOverrides:
    def test_int_override(self, isolated_config, monkeypatch):
        monkeypatch.setenv("KODE_ESCALATION_MAX_ROUNDS", "2")
        assert isolated_config().escalation.max_rounds == 2

    def test_bool_override(self, isolated_config, monkeypatch):
        monkeypatch.setenv("KODE_ESCALATION_ENABLED", "true")
        assert isolated_config().escalation.enabled is True

    def test_manager_override_is_explicit(self, isolated_config, monkeypatch):
        monkeypatch.setenv("KODE_ESCALATION_MANAGER_PROVIDER", "unsloth")
        assert isolated_config().escalation.manager_provider == "unsloth"


def test_runner_config_bridges_escalation_config():
    from bytia_kode.config import EscalationConfig
    from bytia_kode.orchestrator.runner import RunnerConfig

    escalation = EscalationConfig(
        max_rounds=2, max_tasks=3, max_tokens=1000, max_wallclock_min=1
    )

    config = RunnerConfig.from_escalation(escalation)

    assert config.max_rounds == 2
    assert config.max_tasks == 3
    assert config.max_tokens == 1000
    assert config.max_wallclock_s == 60
