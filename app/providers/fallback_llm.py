from __future__ import annotations

from typing import Any


def call_fallback(payload: dict[str, Any]) -> dict[str, Any]:
    """Ultra-fast, deterministic fallback response."""
    prompt = (payload or {}).get("prompt", "").strip()
    if not prompt:
        text = "[FALLBACK] I’m here and responsive. Try again in a moment."
    else:
        sample = prompt[:80].replace("\n", " ")
        text = f"[FALLBACK] Quick tip: stay consistent. (You said: “{sample}…”)"
    return {"text": text}
