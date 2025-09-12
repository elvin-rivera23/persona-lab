# app/safety/taxonomy.py
from typing import Any

from .exit_reasons import SafetyExitReason

# Client-facing taxonomy for handling exits. Keep aligned with SafetyExitReason.
_TAXONOMY: dict[str, dict[str, Any]] = {
    SafetyExitReason.KILL_SWITCH.value: {
        "severity": "high",
        "description": "Operator disabled generation via kill switch.",
        "client_action": "Show a friendly outage banner; retry later.",
    },
    SafetyExitReason.PROMPT_TOO_LONG.value: {
        "severity": "low",
        "description": "Prompt length exceeds configured limit.",
        "client_action": "Ask user to shorten input; consider chunking.",
    },
    SafetyExitReason.POLICY_VIOLATION.value: {
        "severity": "medium",
        "description": "Denylist/policy phrase detected.",
        "client_action": "Redact or rephrase; show policy hint.",
    },
    SafetyExitReason.SENSITIVE_PII.value: {
        "severity": "high",
        "description": "Possible sensitive PII detected (e.g., SSN/credit card).",
        "client_action": "Block; advise removing PII before retry.",
    },
    SafetyExitReason.JAILBREAK_DETECTED.value: {
        "severity": "medium",
        "description": "Prompt-injection/jailbreak cue detected.",
        "client_action": "Suggest safer phrasing; remove jailbreak cues.",
    },
    SafetyExitReason.LATENCY_BUDGET.value: {
        "severity": "low",
        "description": "Request exceeded latency budget.",
        "client_action": "Offer retry or streaming; widen budget if needed.",
    },
    SafetyExitReason.TOKEN_BUDGET.value: {
        "severity": "low",
        "description": "Estimated token budget exceeded.",
        "client_action": "Shorten input/context or increase budget.",
    },
    SafetyExitReason.COST_BUDGET.value: {
        "severity": "low",
        "description": "Estimated cost exceeded configured budget.",
        "client_action": "Confirm spend or pick a cheaper path.",
    },
    SafetyExitReason.RATE_LIMIT.value: {
        "severity": "low",
        "description": "Too many requests.",
        "client_action": "Backoff and retry later.",
    },
    SafetyExitReason.MALFORMED_INPUT.value: {
        "severity": "low",
        "description": "Input didn’t pass validation/hygiene.",
        "client_action": "Fix input shape/encoding and retry.",
    },
    SafetyExitReason.UNSPECIFIED.value: {
        "severity": "low",
        "description": "Generic safety exit (unspecified).",
        "client_action": "Retry or contact support with request ID.",
    },
}


def get_taxonomy() -> list[dict[str, Any]]:
    return [{"reason": reason, **payload} for reason, payload in _TAXONOMY.items()]
