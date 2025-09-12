# app/safety/patterns.py
import re

# --- PII (coarse, demo-grade; refine later) ---
# US SSN: 3-2-4 digits with optional dashes/spaces
SSN_RE = re.compile(r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b")

# Credit card (rough): 13-19 digits ignoring spaces/dashes
CC_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

# --- Jailbreak / prompt-injection cues (starter set) ---
JAILBREAK_PHRASES = [
    "ignore previous instructions",
    "disregard your rules",
    "break character",
    "jailbreak",
    "do anything now",
    "developer mode",
    "bypass safety",
    "as an ai with no restrictions",
]


def contains_pii(text: str) -> str | None:
    if SSN_RE.search(text):
        return "ssn_pattern"
    if CC_RE.search(text):
        return "credit_card_pattern"
    return None


def contains_jailbreak(text: str) -> str | None:
    t = text.lower()
    for phrase in JAILBREAK_PHRASES:
        if phrase in t:
            return phrase
    return None
