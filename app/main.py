# app/main.py
from __future__ import annotations

import json
import os
import platform
import random
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response, status

# Personality catalog (ASCII + quotes/tips + picker)
from app.worker.personality import ASCII_LOGO, QUOTES, TIPS, pick_by_day

APP_NAME = "persona-lab"
APP_DESC = "A tiny FastAPI service that is portable to Raspberry Pi and PC — now with personality."
APP_VERSION_FILE = Path(__file__).resolve().parents[1] / "VERSION"


def read_version_fallback() -> str:
    try:
        return APP_VERSION_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return "0.0.0"


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


# Env-configured runtime info (keeps tests portable while providing sensible defaults)
HOST = os.getenv("APP_HOST", "0.0.0.0")
PORT = int(os.getenv("APP_PORT", "8001"))
WORKERS = int(os.getenv("APP_WORKERS", "1"))

app = FastAPI(
    title=APP_NAME,
    description=APP_DESC,
    version=read_version_fallback(),
)

# -------------------------
# Core endpoints (preserve contract expected by tests)
# -------------------------


@app.get("/health", tags=["core"])
def health():
    # Tests expect exactly {"status": "ok"}
    return {"status": "ok"}


@app.get("/version", tags=["core"])
def version():
    # Tests expect these keys present
    return {
        "service": APP_NAME,
        "version": read_version_fallback(),
        "host": HOST,
        "port": PORT,
        "workers": WORKERS,
    }


@app.get("/__meta", tags=["core"])
def meta():
    # Tests expect keys: service, version, git, build, runtime, endpoints
    git_commit = os.getenv("GIT_COMMIT", "unknown")
    git_sha = os.getenv("GIT_SHA", git_commit)  # alias to satisfy tests expecting `sha`
    git = {
        "commit": git_commit,
        "sha": git_sha,
        "branch": os.getenv("GIT_BRANCH", "unknown"),
        "dirty": os.getenv("GIT_DIRTY", "unknown"),
    }
    build = {
        "time": os.getenv("BUILD_TIME", "unknown"),
        "containerized": Path("/.dockerenv").exists(),
    }
    runtime = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "pid": os.getpid(),
        "as_of": utc_now_iso(),
    }
    # Only include API paths (filter out duplicates and include fun routes too)
    endpoints = sorted(
        {getattr(r, "path", "") for r in app.routes if getattr(r, "path", "").startswith("/")}
    )
    return {
        "service": APP_NAME,
        "version": read_version_fallback(),
        "git": git,
        "build": build,
        "runtime": runtime,
        "endpoints": endpoints,
    }


# -------------------------
# Personality & Fun pack
# -------------------------

GREET_TAGLINES = [
    "Let’s ship something cool today.",
    "Pi-first, portable everywhere.",
    "Small service, big DevOps energy.",
    "Clean APIs, clean logs, clean gains.",
]

EMOJI_MAP = {
    "happy": "😄",
    "sad": "😔",
    "cool": "😎",
    "party": "🥳",
    "thinking": "🤔",
}


@app.get("/fun/greet", tags=["fun"])
def fun_greet(name: str = Query("friend", min_length=1, max_length=40)):
    # Rotate deterministically per-minute for light variability without flakiness.
    idx = int(datetime.now(UTC).strftime("%M")) % len(GREET_TAGLINES)
    tagline = GREET_TAGLINES[idx]
    return {"message": f"Hey {name}!", "tagline": tagline, "as_of": utc_now_iso()}


@app.get("/fun/emoji", tags=["fun"])
def fun_emoji(mood: str = Query(..., description=f"One of: {', '.join(EMOJI_MAP.keys())}")):
    key = mood.lower().strip()
    if key not in EMOJI_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported mood '{mood}'. Allowed: {', '.join(EMOJI_MAP.keys())}",
        )
    return {"mood": key, "emoji": EMOJI_MAP[key], "as_of": utc_now_iso()}


@app.get("/fun/roll", tags=["fun"])
def fun_roll(
    d: int = Query(6, ge=2, le=1000, description="Dice sides"),
    n: int = Query(1, ge=1, le=100, description="Number of dice"),
):
    rng = random.SystemRandom()
    rolls: list[int] = [rng.randrange(1, d + 1) for _ in range(n)]
    return {"sides": d, "count": n, "rolls": rolls, "total": sum(rolls)}


@app.get("/fun/teapot", tags=["fun"])
def fun_teapot():
    # RFC 2324 — Hyper Text Coffee Pot Control Protocol (HTCPCP)
    payload = {"message": "I’m a teapot ☕ → 🫖", "code": 418, "as_of": utc_now_iso()}
    return Response(
        content=json.dumps(payload),
        media_type="application/json",
        status_code=status.HTTP_418_IM_A_TEAPOT,
    )


@app.get("/fun/motd", tags=["fun"])
def fun_motd():
    """Message of the day with ASCII logo, quote, tip, and minimal build context."""
    quote = pick_by_day(QUOTES)
    tip = pick_by_day(TIPS)
    return {
        "logo": ASCII_LOGO.strip("\n"),
        "quote": quote,
        "tip": tip,
        "build": {
            "service": APP_NAME,
            "version": read_version_fallback(),
        },
        "as_of": utc_now_iso(),
    }
