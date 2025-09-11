from __future__ import annotations

import logging
import os
import platform
import random
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.engagement import get_feedback_summary, get_recent_feedback, init_db, insert_feedback
from app.personas.playful import respond as playful_respond

# Personas
from app.personas.serious import respond as serious_respond

# A/B policy engine
from app.policy.ab import assign_ab, get_policy

# Personality catalog (ASCII + quotes/tips + picker)
from app.worker.personality import ASCII_LOGO, QUOTES, TIPS

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
# Logging (for A/B events too)
# -------------------------
log = logging.getLogger("persona_lab")
if not log.handlers:
    handler = logging.StreamHandler()
    fmt = logging.Formatter('{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}')
    handler.setFormatter(fmt)
    log.addHandler(handler)
    log.setLevel(logging.INFO)

# -------------------------
# Feedback models & startup
# -------------------------


class FeedbackIn(BaseModel):
    session_id: str | None = Field(None, description="Opaque session identifier")
    interaction_id: str | None = Field(None, description="Optional prior interaction id")
    score: int = Field(..., ge=1, le=5, description="Feedback score 1..5")
    notes: str | None = Field(None, description="Optional free-text notes")


class FeedbackOut(BaseModel):
    status: str
    feedback_id: str


# ---- A/B Models (for blending experiments)
class ABRequest(BaseModel):
    user_id: str
    prompt: str
    deterministic: bool | None = False  # if True, always pick top-weight policy


class ABResponse(BaseModel):
    group: str
    picked_policy: str
    policy_weights: dict[str, float]
    response: dict[str, Any]
    took_ms: int


@app.on_event("startup")
def _init_engagement_db():
    init_db()


# -------------------------
# Core endpoints
# -------------------------


@app.get("/health", tags=["core"])
def health():
    return {"status": "ok"}


@app.get("/version", tags=["core"])
def version():
    return {
        "service": APP_NAME,
        "version": read_version_fallback(),
        "host": HOST,
        "port": PORT,
        "workers": WORKERS,
    }


@app.get("/__meta", tags=["core"])
def meta():
    git_commit = os.getenv("GIT_COMMIT", "unknown")
    git_sha = os.getenv("GIT_SHA", git_commit)
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
# Feedback endpoints
# -------------------------


@app.post("/feedback", response_model=FeedbackOut, tags=["core"])
def post_feedback(payload: FeedbackIn):
    try:
        fid = insert_feedback(
            interaction_id=payload.interaction_id,
            session_id=payload.session_id,
            score=payload.score,
            notes=payload.notes,
        )
        return {"status": "ok", "feedback_id": fid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to record feedback: {e}") from e


@app.get("/engagement/summary", tags=["core"])
def engagement_summary(
    window_seconds: int | None = Query(None, ge=1, le=31536000),
    limit: int = Query(10, ge=1, le=200),
):
    try:
        summary = get_feedback_summary(window_seconds=window_seconds)
        recent = get_recent_feedback(limit=limit)
        return {"summary": summary, "recent": recent}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"failed to compute engagement summary: {e}"
        ) from e


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
    idx = int(datetime.now(UTC).strftime("%M")) % len(GREET_TAGLINES)
    tagline = GREET_TAGLINES[idx]
    return {"message": f"Hey {name}!", "tagline": tagline, "as_of": utc_now_iso()}


@app.get("/fun/motd", tags=["fun"])
def fun_motd():
    day_idx = datetime.now(UTC).timetuple().tm_yday % len(QUOTES)
    quote = QUOTES[day_idx]
    tip = TIPS[day_idx % len(TIPS)]
    return {"logo": ASCII_LOGO, "quote": quote, "tip": tip, "as_of": utc_now_iso()}


@app.get("/fun/teapot", tags=["fun"])
def fun_teapot():
    if random.random() < 0.5:
        return Response(content="I'm not a teapot.", status_code=status.HTTP_200_OK)
    return Response(content="I'm a teapot! ☕", status_code=status.HTTP_418_IM_A_TEAPOT)


@app.get("/fun/playground", response_class=HTMLResponse, tags=["fun"])
def fun_playground():
    html = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Persona Lab Playground</title>
  ...
</html>"""
    return HTMLResponse(content=html, status_code=200)


# -------------------------
# A/B policy endpoints
# -------------------------

# In-memory AB counters
AB_COUNTER = Counter()  # key: (group, persona)
AB_TOTAL = Counter()  # key: group
_AB_LOCK = Lock()


@app.get("/policy", tags=["ab"])
def read_policy(name: str = Query("default", description="Policy name to inspect")):
    blender = get_policy(name)
    return {"name": name, "weights": blender.policies}


@app.post("/predict_ab", response_model=ABResponse, tags=["ab"])
def predict_ab(req: ABRequest):
    t0 = time.time()
    group, blender = assign_ab(req.user_id)

    picked = blender.choose_policy(stochastic=not req.deterministic)

    # ---- record metrics
    with _AB_LOCK:
        AB_COUNTER[(group, picked)] += 1
        AB_TOTAL[group] += 1

    # Route to real persona responders
    if picked == "serious":
        text = serious_respond(req.prompt)
    elif picked == "playful":
        text = playful_respond(req.prompt)
    else:
        text = serious_respond(req.prompt)

    resp_payload = {
        "text": text,
        "meta": {"persona": picked, "ab_group": group},
    }

    took_ms = int((time.time() - t0) * 1000)

    log.info(
        f'ab_event user_id="{req.user_id}" group="{group}" picked="{picked}" took_ms={took_ms}'
    )

    return ABResponse(
        group=group,
        picked_policy=picked,
        policy_weights=blender.policies,
        response=resp_payload,
        took_ms=took_ms,
    )


@app.get("/ab/summary", tags=["ab"])
def ab_summary():
    """
    Returns counts since process start by group and persona.
    Reset with POST /ab/reset.
    """
    with _AB_LOCK:
        groups = {}
        for (grp, persona), n in AB_COUNTER.items():
            groups.setdefault(grp, {})[persona] = groups.get(grp, {}).get(persona, 0) + n
        for grp, total in AB_TOTAL.items():
            groups.setdefault(grp, {})["_total"] = total

        grand_total = sum(AB_TOTAL.values())
        return {"groups": groups, "grand_total": grand_total}


@app.post("/ab/reset", tags=["ab"])
def ab_reset():
    """Clears the in-memory counters (useful during demos/tests)."""
    with _AB_LOCK:
        AB_COUNTER.clear()
        AB_TOTAL.clear()
    return {"status": "ok", "message": "AB counters reset"}
