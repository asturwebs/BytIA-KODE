"""Tests for CircuitBreaker — state transitions and recovery logic."""
import time

import pytest

from bytia_kode.providers.circuit import CircuitBreaker


class TestCircuitBreakerStates:
    def test_starts_closed(self):
        cb = CircuitBreaker()
        assert cb.state == "closed"

    def test_success_keeps_closed(self):
        cb = CircuitBreaker()
        cb.record_success()
        assert cb.state == "closed"
        assert cb.is_available is True

    def test_failures_open_circuit(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        assert cb.state == "closed"
        cb.record_failure()
        assert cb.state == "closed"
        cb.record_failure()
        assert cb.state == "open"
        assert cb.is_available is False

    def test_failure_count_resets_on_success(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"  # Only 2 failures after reset

    def test_recovery_to_half_open(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        assert cb.state == "open"
        time.sleep(0.02)
        assert cb.is_available is True
        assert cb.state == "half_open"

    def test_half_open_success_closes(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        assert cb.state == "open"
        time.sleep(0.02)
        _ = cb.is_available  # triggers recovery
        assert cb.state == "half_open"
        cb.record_success()
        assert cb.state == "closed"
        assert cb.is_available is True

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        assert cb.state == "open"
        time.sleep(0.02)
        _ = cb.is_available  # triggers recovery
        assert cb.state == "half_open"
        cb.record_failure()
        assert cb.state == "open"
        assert cb.is_available is False

    def test_open_is_not_available_before_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()
        assert cb.state == "open"
        assert cb.is_available is False
