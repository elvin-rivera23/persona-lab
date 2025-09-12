# app/safety/timeout.py
import time
from collections.abc import Callable
from typing import Any

from .exit_reasons import SafetyExit, SafetyExitReason


def run_with_timeout(
    fn: Callable[[], Any],
    started_ms: int,
    budget_ms: int,
) -> tuple[Any | None, SafetyExit | None]:
    """
    Runs fn(); if elapsed exceeds budget after call, return a SafetyExit
    instead of the result. Cooperative (soft) timeout for sync work.
    """
    result = fn()
    now = int(time.time() * 1000)
    if now - started_ms > budget_ms:
        return None, SafetyExit(
            reason=SafetyExitReason.LATENCY_BUDGET,
            severity="low",
            message="Latency budget exceeded during generation.",
            details={"elapsed_ms": now - started_ms, "budget_ms": budget_ms},
        )
    return result, None
