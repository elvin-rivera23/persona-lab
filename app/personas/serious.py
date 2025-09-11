# app/personas/serious.py

from datetime import UTC, datetime


def respond(prompt: str) -> str:
    """
    Serious, concise, to-the-point style.
    """
    ts = datetime.now(UTC).isoformat()
    return f"[SERIOUS] {ts} :: {prompt}\nSummary: {prompt.strip()}."
