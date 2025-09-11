from __future__ import annotations

import logging
import os
import platform
import random
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.ab_track import aggregate_with_feedback, record_interaction
from app.ab_track import init as ab_init
from app.engagement import get_feedback_summary, get_recent_feedback, init_db, insert_feedback
from app.personas.playful import respond as playful_respond
from app.personas.serious import respond as serious_respond
from app.policy.ab import assign_ab, get_policy
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


# Env-configured runtime info
HOST = os.getenv("APP_HOST", "0.0.0.0")
PORT = int(os.getenv("APP_PORT", "8001"))
WORKERS = int(os.getenv("APP_WORKERS", "1"))

app = FastAPI(
    title=APP_NAME,
    description=APP_DESC,
    version=read_version_fallback(),
)

# -------------------------
# Logging
# -------------------------
log = logging.getLogger("persona_lab")
if not log.handlers:
    handler = logging.StreamHandler()
    fmt = logging.Formatter('{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}')
    handler.setFormatter(fmt)
    log.addHandler(handler)
    log.setLevel(logging.INFO)


# -------------------------
# Models & startup
# -------------------------
class FeedbackIn(BaseModel):
    session_id: str | None = Field(None, description="Opaque session identifier")
    interaction_id: str | None = Field(None, description="Optional prior interaction id")
    score: int = Field(..., ge=1, le=5, description="Feedback score 1..5")
    notes: str | None = Field(None, description="Optional free-text notes")


class FeedbackOut(BaseModel):
    status: str
    feedback_id: str


class ABRequest(BaseModel):
    user_id: str
    prompt: str
    session_id: str | None = None  # (7B/7C) allow session attribution
    deterministic: bool | None = False  # if True, always pick top-weight policy


class ABResponse(BaseModel):
    group: str
    picked_policy: str
    policy_weights: dict[str, float]
    response: dict[str, Any]
    took_ms: int
    interaction_id: str  # (7B/7C) used by the UI to tie feedback


@app.on_event("startup")
def _init_engagement_db():
    init_db()
    ab_init()  # ensure ab_interactions + interactions table(s) exist


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
# Fun endpoints (with Playground wired for 7C)
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
    build = {
        "service": "persona-lab",
        "version": read_version_fallback(),
        "host": HOST,
        "port": PORT,
    }
    return {"logo": ASCII_LOGO, "quote": quote, "tip": tip, "build": build, "as_of": utc_now_iso()}


@app.get("/fun/emoji", tags=["fun"])
def fun_emoji(mood: str = Query(..., description="happy|sad|cool|party|thinking")):
    if mood not in EMOJI_MAP:
        raise HTTPException(status_code=400, detail="Unsupported mood")
    return {"mood": mood, "emoji": EMOJI_MAP[mood], "as_of": utc_now_iso()}


@app.get("/fun/roll", tags=["fun"])
def fun_roll(
    d: int = Query(6, ge=2, le=1000, description="sides per die"),
    n: int = Query(1, ge=1, le=100, description="number of dice"),
):
    rolls = [random.randint(1, d) for _ in range(n)]
    return {"sides": d, "count": n, "rolls": rolls, "total": sum(rolls), "as_of": utc_now_iso()}


@app.get("/fun/teapot", tags=["fun"])
def fun_teapot():
    # Tests expect HTTP 418 and JSON including { code: 418 }
    from fastapi.responses import JSONResponse

    body = {"code": 418, "status": "teapot", "message": "I'm a teapot! ☕"}
    return JSONResponse(body, status_code=418)


@app.get("/fun/playground", response_class=HTMLResponse, tags=["fun"])
def fun_playground():
    html = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Persona Lab — Playground</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 24px; }
    h1 { margin-bottom: 0; }
    #logo { font-family: monospace; white-space: pre; }
    #toast { position: fixed; bottom: 16px; left: 50%; transform: translateX(-50%);
             background: #333; color: #fff; padding: 8px 16px; border-radius: 8px; display: none; }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .card { border: 1px solid #ddd; border-radius: 12px; padding: 16px; max-width: 900px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06); margin-top: 16px; }
    button { padding: 8px 12px; border-radius: 8px; border: 1px solid #ccc; background: #fafafa; cursor: pointer; }
    button:hover { background: #f0f0f0; }
    textarea { width: 100%; min-height: 60px; }
    .muted { color: #666; font-size: 0.9em; }
    .pill { border: 1px solid #ddd; border-radius: 999px; padding: 4px 10px; }
  </style>
</head>
<body>
  <h1>Persona Lab — Playground</h1>
  <pre id="logo"></pre>

  <div class="card">
    <h3>Quote of the day</h3>
    <p><strong>Quote:</strong> <span id="motd-quote"></span></p>
    <p><strong>Tip:</strong> <span id="motd-tip"></span></p>
    <div class="row"><button id="brew-418">Brew a 418</button><div id="teapot-out" class="pill"></div></div>
  </div>

  <div class="card">
    <h3>Engagement</h3>
    <div class="row">
      <span class="pill">Session: <code id="session-id"></code></span>
      <span class="pill">Count: <span id="sum-count">—</span></span>
      <span class="pill">Avg score: <span id="sum-avg">—</span></span>
      <span class="pill">Last updated: <span id="sum-asof">—</span></span>
    </div>
    <div class="row" style="margin-top:10px;">
      <button id="thumbs-up">👍 Thumbs Up</button>
      <button id="thumbs-down">👎 Thumbs Down</button>
    </div>
    <p class="muted">Optional notes:</p>
    <textarea id="notes" placeholder="What made it good/bad? (stored with your score)"></textarea>
  </div>

  <div id="toast"></div>
  <canvas id="confetti"></canvas>

<script>
let currentInteractionId = null;

function getSessionId() {
  try {
    let s = localStorage.getItem('plab_sess');
    if (!s) {
      s = 'sess-' + Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
      localStorage.setItem('plab_sess', s);
    }
    return s;
  } catch (e) { return 'sess-anon'; }
}

async function loadMOTD() {
  const r = await fetch('/fun/motd');
  if (!r.ok) throw new Error('motd failed');
  const data = await r.json();
  document.getElementById('logo').textContent = data.logo || '';
  document.getElementById('motd-quote').textContent = data.quote || '';
  document.getElementById('motd-tip').textContent = data.tip || '';
}

async function brew418() {
  const r = await fetch('/fun/teapot');
  const txt = await r.text();
  document.getElementById('teapot-out').textContent = txt;
  if (r.status === 418) {
    toast('418: I\\'m a teapot ☕');
    confetti();
  } else {
    toast('Not a teapot: ' + r.status);
  }
}

async function predict(promptText) {
  // Call /predict_ab and capture the interaction_id for attribution
  const sess = getSessionId();
  const r = await fetch('/predict_ab', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ user_id: sess, session_id: sess, prompt: promptText || 'Hello!' })
  });
  if (!r.ok) {
    toast('Prediction failed');
    return null;
  }
  const data = await r.json();
  currentInteractionId = data.interaction_id || null;
  return data;
}

async function refreshSummary() {
  const r = await fetch('/engagement/summary?limit=5');
  if (!r.ok) return;
  const data = await r.json();
  const sum = data.summary || {};
  document.getElementById('sum-count').textContent = (sum.count ?? '—');
  document.getElementById('sum-avg').textContent = (sum.avg_score != null ? sum.avg_score.toFixed(2) : '—');
  document.getElementById('sum-asof').textContent = new Date((sum.as_of||0)*1000).toLocaleTimeString();
}

async function sendFeedback(score) {
  // Ensure we have an active interaction; if not, fetch one
  if (!currentInteractionId) {
    await predict('Hello!');
  }
  const sess = getSessionId();
  const notes = document.getElementById('notes').value || null;
  const payload = {
    interaction_id: currentInteractionId,
    session_id: sess,
    score: score,
    notes: notes
  };
  const r = await fetch('/feedback', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  if (r.ok) {
    toast('Thanks for the feedback!');
    if (score >= 5) confetti();
    document.getElementById('notes').value = '';
    refreshSummary();
  } else {
    const txt = await r.text();
    toast('Feedback failed: ' + txt);
  }
}

function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.style.display = 'block';
  setTimeout(() => el.style.display = 'none', 1800);
}

function confetti() {
  const c = document.getElementById('confetti');
  const ctx = c.getContext('2d');
  const W = c.width = window.innerWidth;
  const H = c.height = window.innerHeight;
  const N = 80;
  const parts = Array.from({length: N}, () => ({
    x: Math.random() * W,
    y: -20 - Math.random()*H*0.3,
    vx: (Math.random()-0.5)*2,
    vy: 2 + Math.random()*3,
    r: 2 + Math.random()*3
  }));
  let t = 0;
  const id = setInterval(() => {
    t++;
    ctx.clearRect(0,0,W,H);
    for (const p of parts) {
      p.x += p.vx; p.y += p.vy;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI*2); ctx.fill();
    }
    if (t > 90) clearInterval(id);
  }, 16);
}

document.getElementById('brew-418').addEventListener('click', brew418);
document.getElementById('thumbs-up').addEventListener('click', () => sendFeedback(5));
document.getElementById('thumbs-down').addEventListener('click', () => sendFeedback(1));
document.getElementById('session-id').textContent = getSessionId();

// Boot: load MOTD, pull summary, and pre-create an interaction_id for this session
loadMOTD().catch(() => toast('Failed to load MOTD'));
refreshSummary().catch(()=>{});
predict('Hello!').catch(()=>{});
</script>
</body>
</html>
"""
    return HTMLResponse(content=html, status_code=200)


# -------------------------
# A/B policy endpoints (with interaction_id + attribution)
# -------------------------
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

    # record in-memory counts
    with _AB_LOCK:
        AB_COUNTER[(group, picked)] += 1
        AB_TOTAL[group] += 1

    # route to persona responders
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

    # NEW (7B): persist interaction for FK + leaderboard attribution
    interaction_id = str(uuid.uuid4())
    try:
        record_interaction(
            interaction_id=interaction_id,
            ab_group=group,
            persona=picked,
            session_id=req.session_id,
        )
    except Exception as e:
        log.error(f'ab_track_error interaction_id="{interaction_id}" err="{e}"')

    log.info(
        f'ab_event user_id="{req.user_id}" group="{group}" picked="{picked}" took_ms={took_ms}'
    )

    return ABResponse(
        group=group,
        picked_policy=picked,
        policy_weights=blender.policies,
        response=resp_payload,
        took_ms=took_ms,
        interaction_id=interaction_id,  # (7B/7C) UI will send this back to /feedback
    )


@app.get("/ab/summary", tags=["ab"])
def ab_summary():
    """Returns counts since process start by group and persona."""
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


# NEW (7B): leaderboard endpoint (variant-aware)
@app.get("/leaderboard", tags=["ab"])
def leaderboard(days: int = Query(30, ge=1, le=365)):
    """
    Aggregated feedback per A/B group and persona using a Wilson lower bound
    for 'positive' rate (score >= 4) plus average score.
    """
    rows = aggregate_with_feedback(limit_days=days)
    return {"as_of": utc_now_iso(), "days": days, "results": rows}
