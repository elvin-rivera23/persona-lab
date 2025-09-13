from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

from .circuit_breaker import BreakerConfig, CircuitBreaker

# ---- Config via env (with safe defaults)
TIMEOUT_SECS = float(os.getenv("LLM_TIMEOUT_SECS", "8"))
RETRY_MAX_ATTEMPTS = int(os.getenv("LLM_RETRY_MAX_ATTEMPTS", "2"))
RETRY_BACKOFF_BASE_MS = int(os.getenv("LLM_RETRY_BACKOFF_BASE_MS", "200"))
CB_WINDOW_SECONDS = int(os.getenv("LLM_CB_WINDOW_SECONDS", "30"))
CB_FAILURE_THRESHOLD = float(os.getenv("LLM_CB_FAILURE_THRESHOLD", "0.5"))
CB_MIN_CALLS = int(os.getenv("LLM_CB_MIN_CALLS", "6"))
CB_HALFOPEN_AFTER_SECONDS = int(os.getenv("LLM_CB_HALFOPEN_AFTER_SECONDS", "15"))
LATENCY_BUDGET_MS = int(os.getenv("LLM_LATENCY_BUDGET_MS", "2500"))

# Only retry on truly transient errors
TRANSIENT_ERRORS = (TimeoutError, ConnectionError)


class CallError(Exception):
    pass


class LLMClient:
    def __init__(self, fn_call_model: Callable[[dict[str, Any], float], dict[str, Any]]):
        self._call = fn_call_model
        self._breaker = CircuitBreaker(
            BreakerConfig(
                window_seconds=CB_WINDOW_SECONDS,
                failure_threshold=CB_FAILURE_THRESHOLD,
                min_calls=CB_MIN_CALLS,
                halfopen_after_seconds=CB_HALFOPEN_AFTER_SECONDS,
            )
        )

    def call(self, payload: dict[str, Any]) -> dict[str, Any]:
        start = time.time()
        if not self._breaker.allow_request():
            raise CallError("circuit_open")

        attempts = 0
        backoff_ms = RETRY_BACKOFF_BASE_MS
        last_exc: BaseException | None = None

        while True:
            attempts += 1
            try:
                result = self._call(payload, TIMEOUT_SECS)
                self._breaker.record_success()
                elapsed_ms = int((time.time() - start) * 1000)
                return {
                    "ok": True,
                    "result": result,
                    "meta": {
                        "attempts": attempts,
                        "elapsed_ms": elapsed_ms,
                        "breaker_state": self._breaker.state,
                    },
                }
            except TRANSIENT_ERRORS as e:
                last_exc = e
                self._breaker.record_failure()
                if attempts > (1 + RETRY_MAX_ATTEMPTS):
                    break
                time.sleep(backoff_ms / 1000.0)
                backoff_ms *= 2
            except Exception as e:
                last_exc = e
                self._breaker.record_failure()
                break

        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "ok": False,
            "error": str(last_exc) if last_exc else "unknown_error",
            "meta": {
                "attempts": attempts,
                "elapsed_ms": elapsed_ms,
                "breaker_state": self._breaker.state,
            },
        }

    def latency_budget_exceeded(self, meta: dict[str, Any]) -> bool:
        return int(meta.get("elapsed_ms", 0)) > LATENCY_BUDGET_MS
