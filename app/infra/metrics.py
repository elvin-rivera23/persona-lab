# app/infra/metrics.py
from __future__ import annotations

import threading
import time
from collections import Counter, deque
from statistics import median


class InferenceMetrics:
    """
    Minimal, thread-safe in-memory metrics for inference:
      - counters by outcome: primary | fallback_error | fallback_latency_budget | cache_hit
      - breaker states seen (closed/open/half_open)
      - attempts histogram (1, 2, 3, ...)
      - latency samples (ms) per outcome + overall (capped reservoir)
    """

    def __init__(self, max_samples: int = 1000):
        self._lock = threading.Lock()
        self._counters = Counter()  # outcome counters
        self._breaker = Counter()  # breaker state counters
        self._attempts = Counter()  # attempt count distribution

        self._overall_lat: deque[int] = deque(maxlen=max_samples)
        self._by_outcome_lat: dict[str, deque[int]] = {
            "primary": deque(maxlen=max_samples),
            "fallback_error": deque(maxlen=max_samples),
            "fallback_latency_budget": deque(maxlen=max_samples),
            "cache_hit": deque(maxlen=max_samples),
        }

        self._started_at = time.time()

    def record(
        self,
        outcome: str,
        elapsed_ms: int | None = None,
        breaker_state: str | None = None,
        attempts: int | None = None,
    ) -> None:
        with self._lock:
            self._counters[outcome] += 1
            if breaker_state:
                self._breaker[breaker_state] += 1
            if attempts:
                self._attempts[attempts] += 1
            if elapsed_ms is not None:
                self._overall_lat.append(elapsed_ms)
                if outcome in self._by_outcome_lat:
                    self._by_outcome_lat[outcome].append(elapsed_ms)

    @staticmethod
    def _percentile(samples: list[int], p: float) -> int | None:
        if not samples:
            return None
        k = max(0, min(len(samples) - 1, int(round((p / 100.0) * (len(samples) - 1)))))
        return sorted(samples)[k]

    def _lat_summary(self, samples: deque[int]) -> dict[str, int | None]:
        data = list(samples)
        if not data:
            return {"count": 0, "p50": None, "p95": None, "max": None}
        return {
            "count": len(data),
            "p50": int(median(data)),
            "p95": self._percentile(data, 95),
            "max": max(data),
        }

    def snapshot(self) -> dict:
        with self._lock:
            overall = self._lat_summary(self._overall_lat)
            by_outcome = {k: self._lat_summary(v) for k, v in self._by_outcome_lat.items()}
            return {
                "as_of": int(time.time()),
                "uptime_seconds": int(time.time() - self._started_at),
                "counters": dict(self._counters),
                "breaker_states": dict(self._breaker),
                "attempts_hist": dict(self._attempts),
                "latency": {
                    "overall": overall,
                    "by_outcome": by_outcome,
                },
            }


# singletons are fine for this simple service
metrics = InferenceMetrics()
