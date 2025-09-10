# app/worker/personality.py
from __future__ import annotations

from datetime import UTC, datetime

# Clear, readable ASCII logo for "persona-lab"
ASCII_LOGO = r"""
______                                 _           _
| ___ \                               | |         | |
| |_/ /__ _ __ ___  ___  _ __   __ _  | |     __ _| |__
|  __/ _ \ '__/ __|/ _ \| '_ \ / _` | | |    / _` | '_ \
| | |  __/ |  \__ \ (_) | | | | (_| | | |___| (_| | |_) |
\_|  \___|_|  |___/\___/|_| |_|\__,_| \_____/\__,_|_.__/


"""

QUOTES = [
    "Small services, big impact.",
    "Ship it clean, ship it fast.",
    "Portability first: Pi and PC.",
    "Logs tell the story—keep them tidy.",
    "Tests are tiny guardrails for big moves.",
]

TIPS = [
    "Use `python -m pytest` to avoid PATH issues.",
    "Compose profiles keep Pi vs dev clean.",
    "Pin versions in requirements for reproducibility.",
    "Health endpoints are SLO canaries—treat them well.",
    "Prefer structured JSON logs for grep-ability.",
]


def pick_by_day(items: list[str]) -> str:
    """Deterministic rotation by UTC day-of-year."""
    if not items:
        return ""
    day = int(datetime.now(UTC).strftime("%j"))
    return items[day % len(items)]
