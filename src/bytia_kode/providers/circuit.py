"""Circuit breaker for provider resilience."""
from __future__ import annotations

import time


class CircuitBreaker:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 60.0):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failure_count: int = 0
        self._state: str = self.CLOSED
        self._last_failure_time: float = 0.0

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_available(self) -> bool:
        if self._state == self.CLOSED:
            return True
        if self._state == self.OPEN:
            if time.monotonic() - self._last_failure_time >= self._recovery_timeout:
                self._state = self.HALF_OPEN
                return True
            return False
        if self._state == self.HALF_OPEN:
            return True
        return False

    def record_success(self) -> None:
        self._failure_count = 0
        if self._state == self.HALF_OPEN:
            self._state = self.CLOSED

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._state == self.HALF_OPEN:
            self._state = self.OPEN
        elif self._failure_count >= self._failure_threshold:
            self._state = self.OPEN

    def force_open(self) -> None:
        self._state = self.OPEN
        self._failure_count = self._failure_threshold
        self._last_failure_time = time.monotonic()
