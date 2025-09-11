# app/personas/playful.py

import random
from datetime import UTC, datetime

EMOJIS = ["😄", "😎", "🔥", "🚀", "✨", "💡", "🥳"]


def respond(prompt: str) -> str:
    """
    Playful, upbeat style with a tiny splash of emoji.
    """
    ts = datetime.now(UTC).isoformat()
    e = random.choice(EMOJIS)
    return f"[PLAYFUL] {ts} {e}\n{prompt}\nHot take: That’s fun — let’s riff! {e}"
