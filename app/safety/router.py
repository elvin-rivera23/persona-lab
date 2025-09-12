# app/safety/router.py
import time
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.config import settings
from app.safety.guard import SafetyGuard

router = APIRouter(tags=["safety"])


# ----- Schemas -----
class GenerateRequest(BaseModel):
    persona: str | None = "default"
    prompt: str
    latency_budget_ms: int | None = None


class GenerateResponse(BaseModel):
    exit: dict[str, Any] | None = None
    output: str | None = None
    meta: dict[str, Any]


# ----- Safety Guard Instance -----
_guard = SafetyGuard(
    max_prompt_chars=settings.SAFETY_MAX_PROMPT_CHARS,
    denylist=settings.SAFETY_DENYLIST,
)


@router.post("/generate", response_model=GenerateResponse)
async def safety_generate(req: GenerateRequest, request: Request):
    started_ms = int(time.time() * 1000)
    latency_budget_ms = req.latency_budget_ms or settings.SAFETY_DEFAULT_LATENCY_BUDGET_MS

    # SAFETY PREFLIGHT
    exit_obj = _guard.preflight(
        prompt=req.prompt,
        latency_budget_ms=latency_budget_ms,
        started_at_ms=started_ms,
        extras={"persona": req.persona},
    )
    if exit_obj:
        return GenerateResponse(
            exit=exit_obj.to_dict(),
            output=None,
            meta={
                "persona": req.persona,
                "elapsed_ms": int(time.time() * 1000) - started_ms,
                "version": request.app.version if hasattr(request.app, "version") else "0.8.0",
            },
        )

    # Placeholder generation — echo to prove the wiring works.
    fake_output = f"[persona={req.persona}] ECHO: {req.prompt}"

    return GenerateResponse(
        exit=None,
        output=fake_output,
        meta={
            "persona": req.persona,
            "elapsed_ms": int(time.time() * 1000) - started_ms,
            "version": request.app.version if hasattr(request.app, "version") else "0.8.0",
        },
    )
