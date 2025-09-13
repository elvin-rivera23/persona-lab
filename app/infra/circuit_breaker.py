# app/infra/circuit_breaker.py
# Simple in-process circuit breaker with a rolling window.
# Tracks successes/failures and decides whether calls should be short-circuited.

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass


@dataclass
class BreakerConfig:
    window_seconds: int = 30
    failure_threshold: float = 0.5
    min_calls: int = 6
    halfopen_after_seconds: int = 15


class CircuitState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, cfg: BreakerConfig):
        self.cfg = cfg
        self._events = deque()  # (ts, success: bool)
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._opened_at = 0.0

    def _prune(self, now: float) -> None:
        """Remove events outside the rolling window."""
        cutoff = now - self.cfg.window_seconds
        while self._events and self._events[0][0] < cutoff:
            self._events.popleft()

    def _stats(self, now: float) -> tuple[int, int]:
        """Return (total_calls_in_window, failures_in_window)."""
        self._prune(now)
        total = len(self._events)
        fails = sum(1 for _, ok in self._events if not ok)
        return total, fails

    def allow_request(self) -> bool:
        """Should we attempt a call right now?"""
        now = time.time()
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                # Move to HALF_OPEN after a cooldown to allow a probe.
                if now - self._opened_at >= self.cfg.halfopen_after_seconds:
                    self._state = CircuitState.HALF_OPEN
                    return True
                return False

            if self._state == CircuitState.HALF_OPEN:
                # Allow a single probe; caller must record outcome.
                return True

            # Defensive default
            return True

    def record_success(self) -> None:
        now = time.time()
        with self._lock:
            self._events.append((now, True))
            # Any success in OPEN or HALF_OPEN closes the breaker.
            if self._state in (CircuitState.OPEN, CircuitState.HALF_OPEN):
                self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        now = time.time()
        with self._lock:
            self._events.append((now, False))
            total, fails = self._stats(now)
            if total >= self.cfg.min_calls and (fails / float(total)) >= self.cfg.failure_threshold:
                # Open the breaker and start cooldown.
                self._state = CircuitState.OPEN
                self._opened_at = now

    @property
    def state(self) -> str:
        with self._lock:
            return self._state
