# app/main.py
from __future__ import annotations

import json
import os
import platform
import random
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse

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


@app.get("/fun/playground", tags=["fun"], response_class=HTMLResponse)
def fun_playground():
    """A tiny HTML playground that calls /fun/motd and /fun/teapot."""
    html = f"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{APP_NAME} — Playground</title>
<meta name="viewport" content="width=device-width,initial-scale=1" />
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; margin: 24px; }}
  pre#logo {{ white-space: pre; font-size: 12px; line-height: 1.1; margin: 0 0 8px 0; }}
  .card {{ border: 1px solid #8884; border-radius: 12px; padding: 16px; margin: 12px 0; }}
  button {{ padding: 8px 12px; border-radius: 8px; cursor: pointer; }}
  #toast {{ position: fixed; right: 12px; bottom: 12px; background: #333; color:#fff; padding: 8px 12px; border-radius: 8px; display:none; }}
  canvas#confetti {{ position: fixed; inset: 0; pointer-events: none; }}
</style>
</head>
<body>
  <h1>Persona Lab — Playground</h1>

  <div class="card">
    <pre id="logo"></pre>
    <div><strong>Quote:</strong> <span id="motd-quote">loading…</span></div>
    <div><strong>Tip:</strong> <span id="motd-tip">loading…</span></div>
  </div>

  <div class="card">
    <button id="brew-418">Brew a 418</button>
    <pre id="teapot-out"></pre>
  </div>

  <div id="toast"></div>
  <canvas id="confetti"></canvas>

<script>
async function loadMOTD() {{
  const r = await fetch('/fun/motd');
  if (!r.ok) throw new Error('motd failed');
  const data = await r.json();
  document.getElementById('logo').textContent = data.logo || '';
  document.getElementById('motd-quote').textContent = data.quote || '';
  document.getElementById('motd-tip').textContent = data.tip || '';
}}

async function brew418() {{
  const r = await fetch('/fun/teapot');
  const txt = await r.text();
  document.getElementById('teapot-out').textContent = txt;
  if (r.status === 418) {{
    toast('418: I\\'m a teapot ☕');
    confetti();
  }} else {{
    toast('Not a teapot: ' + r.status);
  }}
}}

function toast(msg) {{
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.style.display = 'block';
  setTimeout(() => el.style.display = 'none', 1800);
}}

function confetti() {{
  const c = document.getElementById('confetti');
  const ctx = c.getContext('2d');
  const W = c.width = window.innerWidth;
  const H = c.height = window.innerHeight;
  const N = 80;
  const parts = Array.from({{length: N}}, () => ({{
    x: Math.random() * W,
    y: -20 - Math.random()*H*0.3,
    vx: (Math.random()-0.5)*2,
    vy: 2 + Math.random()*3,
    r: 2 + Math.random()*3
  }}));
  let t = 0;
  const id = setInterval(() => {{
    t++;
    ctx.clearRect(0,0,W,H);
    for (const p of parts) {{
      p.x += p.vx;
      p.y += p.vy;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI*2);
      ctx.fill();
    }}
    if (t > 90) clearInterval(id);
  }}, 16);
}}

document.getElementById('brew-418').addEventListener('click', brew418);
loadMOTD().catch(() => toast('Failed to load MOTD'));
</script>
</body>
</html>
    """
    return HTMLResponse(content=html, status_code=200)
