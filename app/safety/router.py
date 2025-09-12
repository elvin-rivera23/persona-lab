# app/safety/router.py
import time
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.config import settings
from app.safety.exit_reasons import SafetyExit
from app.safety.guard import SafetyGuard
from app.safety.timeout import run_with_timeout

# Try hooking Milestone 7 logger
try:
    from app.ab_track import record_interaction  # existing analytics sink

    HAVE_METRICS = True
except Exception:
    HAVE_METRICS = False

router = APIRouter(tags=["safety"])


class GenerateRequest(BaseModel):
    persona: str | None = "default"
    prompt: str
    latency_budget_ms: int | None = None


class GenerateResponse(BaseModel):
    exit: dict[str, Any] | None = None
    output: str | None = None
    meta: dict[str, Any]


_guard = SafetyGuard(
    max_prompt_chars=settings.SAFETY_MAX_PROMPT_CHARS,
    denylist=settings.SAFETY_DENYLIST,
)


def _emit_safety_metric(req: GenerateRequest, exit_obj: SafetyExit, elapsed_ms: int) -> None:
    if not HAVE_METRICS:
        return
    record_interaction(
        persona=req.persona or "default",
        prompt=req.prompt[:2000],
        response="",
        label=f"SAFETY_EXIT:{exit_obj.reason.value}",
        meta={
            "elapsed_ms": elapsed_ms,
            "severity": exit_obj.severity,
            "details": exit_obj.details or {},
        },
    )


@router.post("/generate", response_model=GenerateResponse)
async def safety_generate(req: GenerateRequest, request: Request):
    started_ms = int(time.time() * 1000)
    budget_ms = req.latency_budget_ms or settings.SAFETY_DEFAULT_LATENCY_BUDGET_MS

    # 1) Preflight checks
    exit_obj = _guard.preflight(
        prompt=req.prompt,
        latency_budget_ms=budget_ms,
        started_at_ms=started_ms,
        extras={"persona": req.persona},
    )
    if exit_obj:
        elapsed = int(time.time() * 1000) - started_ms
        _emit_safety_metric(req, exit_obj, elapsed)
        return GenerateResponse(
            exit=exit_obj.to_dict(),
            output=None,
            meta={
                "persona": req.persona,
                "elapsed_ms": elapsed,
                "version": request.app.version if hasattr(request.app, "version") else "0.8.0",
            },
        )

    # 2) Generate with timeout guard (sync demo)
    def _fake_generate():
        return f"[persona={req.persona}] ECHO: {req.prompt}"

    output, during_exit = run_with_timeout(_fake_generate, started_ms, budget_ms)
    elapsed = int(time.time() * 1000) - started_ms

    if during_exit:
        _emit_safety_metric(req, during_exit, elapsed)
        return GenerateResponse(
            exit=during_exit.to_dict(),
            output=None,
            meta={
                "persona": req.persona,
                "elapsed_ms": elapsed,
                "version": request.app.version if hasattr(request.app, "version") else "0.8.0",
            },
        )

    # 3) Success
    return GenerateResponse(
        exit=None,
        output=output,
        meta={
            "persona": req.persona,
            "elapsed_ms": elapsed,
            "version": request.app.version if hasattr(request.app, "version") else "0.8.0",
        },
    )
