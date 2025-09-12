# app/safety/router.py
import time
from typing import Any

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.config import settings
from app.safety.exit_reasons import SafetyExit, SafetyExitReason
from app.safety.guard import SafetyGuard
from app.safety.taxonomy import get_taxonomy
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
    """
    Best-effort emission to Milestone 7 analytics. We don't assume a fixed signature.
    Tries keyword style, then positional; otherwise silently no-ops.
    """
    if not HAVE_METRICS:
        return
    try:
        # Attempt a keyword-based call (one common shape)
        record_interaction(
            persona=req.persona or "default",
            message=req.prompt[:2000],  # avoid giant logs
            response="",
            label=f"SAFETY_EXIT:{exit_obj.reason.value}",
            meta={
                "elapsed_ms": elapsed_ms,
                "severity": exit_obj.severity,
                "details": exit_obj.details or {},
            },
        )
        return
    except TypeError:
        pass
    except Exception:
        return

    # Fallback: positional shape (persona, message, response, label, meta)
    try:
        record_interaction(
            req.persona or "default",
            (req.prompt or "")[:2000],
            "",
            f"SAFETY_EXIT:{exit_obj.reason.value}",
            {
                "elapsed_ms": elapsed_ms,
                "severity": exit_obj.severity,
                "details": exit_obj.details or {},
            },
        )
    except Exception:
        # If analytics signature doesn't match, skip quietly
        return


@router.post("/generate", response_model=GenerateResponse)
async def safety_generate(req: GenerateRequest, request: Request, response: Response):
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
        response.headers["X-Safety-Exit"] = exit_obj.reason.value
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
        response.headers["X-Safety-Exit"] = during_exit.reason.value
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


@router.get("/exits")
async def safety_exits():
    """Public taxonomy so clients know how to handle exits."""
    return {"exits": get_taxonomy()}


@router.get("/config")
async def safety_config():
    """Reflect current safety-related configuration (read-only)."""
    return {
        "kill_switch": settings.SAFETY_KILL_SWITCH,
        "max_prompt_chars": settings.SAFETY_MAX_PROMPT_CHARS,
        "denylist": settings.SAFETY_DENYLIST,
        "default_latency_budget_ms": settings.SAFETY_DEFAULT_LATENCY_BUDGET_MS,
    }


@router.get("/test")
async def safety_test(reason: str = "unspecified"):
    """
    Synthesize a given exit reason for demo/QA without crafting prompts.
    Usage: /safety/test?reason=kill_switch
    """
    try:
        r = SafetyExitReason(reason)
    except ValueError:
        r = SafetyExitReason.UNSPECIFIED

    # Minimal, safe defaults
    severity = {
        SafetyExitReason.KILL_SWITCH: "high",
        SafetyExitReason.SENSITIVE_PII: "high",
        SafetyExitReason.JAILBREAK_DETECTED: "medium",
        SafetyExitReason.POLICY_VIOLATION: "medium",
        SafetyExitReason.PROMPT_TOO_LONG: "low",
        SafetyExitReason.LATENCY_BUDGET: "low",
        SafetyExitReason.TOKEN_BUDGET: "low",
        SafetyExitReason.COST_BUDGET: "low",
        SafetyExitReason.RATE_LIMIT: "low",
        SafetyExitReason.MALFORMED_INPUT: "low",
        SafetyExitReason.UNSPECIFIED: "low",
    }.get(r, "low")

    exit_obj = SafetyExit(
        reason=r,
        severity=severity,
        message=f"Synthesized exit: {r.value}",
        details={"source": "safety_test"},
    )
    return {"exit": exit_obj.to_dict()}
