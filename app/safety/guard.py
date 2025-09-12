# app/safety/guard.py
import os
import time
from typing import Any

from .exit_reasons import SafetyExit, SafetyExitReason
from .patterns import contains_jailbreak, contains_pii


class SafetyGuard:
    """
    Minimal first-pass guard (extended):
      - kill switch via env
      - prompt length limit
      - simple denylist (placeholder for policy)
      - PII & jailbreak pattern checks
      - latency watchdog (budget declared per-request; simulated check)
    """

    def __init__(
        self,
        max_prompt_chars: int = 4000,
        denylist: list[str] | None = None,
        env: dict[str, str] | None = None,
    ):
        self.max_prompt_chars = max_prompt_chars
        self.denylist = [s.lower() for s in (denylist or [])]
        self.env = env or os.environ

    def preflight(
        self,
        prompt: str,
        latency_budget_ms: int | None = None,
        started_at_ms: int | None = None,
        extras: dict[str, Any] | None = None,
    ) -> SafetyExit | None:
        # 1) Global kill switch
        if self.env.get("SAFETY_KILL_SWITCH", "").lower() in ("1", "true", "on"):
            return SafetyExit(
                reason=SafetyExitReason.KILL_SWITCH,
                severity="high",
                message="Safety kill switch active — generation disabled.",
                details={"hint": "Unset SAFETY_KILL_SWITCH to re-enable"},
            )

        # 2) Prompt length
        if len(prompt) > self.max_prompt_chars:
            return SafetyExit(
                reason=SafetyExitReason.PROMPT_TOO_LONG,
                severity="low",
                message=f"Prompt exceeds {self.max_prompt_chars} characters.",
                details={"length": len(prompt)},
            )

        # 3) Simple denylist policy stub
        prompt_l = prompt.lower()
        for word in self.denylist:
            if word in prompt_l:
                return SafetyExit(
                    reason=SafetyExitReason.POLICY_VIOLATION,
                    severity="medium",
                    message="Prompt triggered denylist keyword.",
                    details={"keyword": word},
                )

        # 4) PII detection
        pii_kind = contains_pii(prompt)
        if pii_kind:
            return SafetyExit(
                reason=SafetyExitReason.SENSITIVE_PII,
                severity="high",
                message="Prompt appears to contain sensitive PII.",
                details={"pii": pii_kind},
            )

        # 5) Jailbreak cues
        jb_phrase = contains_jailbreak(prompt)
        if jb_phrase:
            return SafetyExit(
                reason=SafetyExitReason.JAILBREAK_DETECTED,
                severity="medium",
                message="Prompt contains jailbreak/prompt-injection cues.",
                details={"phrase": jb_phrase},
            )

        # 6) Latency watchdog (best-effort, check elapsed so far)
        if latency_budget_ms is not None and started_at_ms is not None:
            now = int(time.time() * 1000)
            if now - started_at_ms > latency_budget_ms:
                return SafetyExit(
                    reason=SafetyExitReason.LATENCY_BUDGET,
                    severity="low",
                    message="Latency budget exceeded before generation.",
                    details={"elapsed_ms": now - started_at_ms, "budget_ms": latency_budget_ms},
                )

        # No exit
        return None
