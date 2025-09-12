# app/config.py
import os


class Settings:
    # Safety defaults (tunable via env)
    SAFETY_KILL_SWITCH: str = os.getenv("SAFETY_KILL_SWITCH", "0")
    SAFETY_MAX_PROMPT_CHARS: int = int(os.getenv("SAFETY_MAX_PROMPT_CHARS", "4000"))

    # Comma-separated denylist: "secret_key, ssn, credit card"
    _denylist = os.getenv("SAFETY_DENYLIST", "").strip()
    SAFETY_DENYLIST: list[str] = (
        [s.strip() for s in _denylist.split(",") if s.strip()] if _denylist else []
    )

    # Default latency budget (ms) if client doesn't provide one
    SAFETY_DEFAULT_LATENCY_BUDGET_MS: int = int(
        os.getenv("SAFETY_DEFAULT_LATENCY_BUDGET_MS", "3500")
    )


settings = Settings()
