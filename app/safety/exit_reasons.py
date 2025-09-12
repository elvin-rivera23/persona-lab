# app/safety/exit_reasons.py
from dataclasses import dataclass
from enum import Enum
from typing import Any


class SafetyExitReason(str, Enum):
    # Content & policy
    POLICY_VIOLATION = "policy_violation"
    JAILBREAK_DETECTED = "jailbreak_detected"
    SENSITIVE_PII = "sensitive_pii"

    # Ops/limits
    RATE_LIMIT = "rate_limit"
    TOKEN_BUDGET = "token_budget"
    COST_BUDGET = "cost_budget"
    LATENCY_BUDGET = "latency_budget"
    KILL_SWITCH = "kill_switch"

    # Input hygiene
    MALFORMED_INPUT = "malformed_input"
    PROMPT_TOO_LONG = "prompt_too_long"

    # Catch-all
    UNSPECIFIED = "unspecified"


@dataclass
class SafetyExit:
    reason: SafetyExitReason
    severity: str  # "low" | "medium" | "high"
    message: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason.value,
            "severity": self.severity,
            "message": self.message,
            "details": self.details or {},
        }
