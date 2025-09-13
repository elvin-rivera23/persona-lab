# app/safety/generate_router.py
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.infra.llm_client import LLMClient
from app.providers.fallback_llm import call_fallback  # ultra-fast deterministic fallback
from app.providers.mock_llm import call_model as mock_call_model  # primary (swap to real later)

log = logging.getLogger("persona_lab.generate")
router = APIRouter(tags=["safety"])

# Shared client instance (respects env knobs from .env/.env.example)
llm = LLMClient(fn_call_model=mock_call_model)


# ---- I/O models
class GenerateRequest(BaseModel):
    prompt: str


class GenerateResponse(BaseModel):
    text: str
    meta: dict


def _mk_meta(source: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Attach a simple, queryable source tag plus any extra metadata."""
    base = {"source": source}
    if extra:
        base.update(extra)
    return base


@router.post("/generate_v2", response_model=GenerateResponse)
def safety_generate(req: GenerateRequest):
    """
    Milestone 9B — Fallback Routing
      1) Try primary via LLMClient (timeout + retries + circuit breaker).
      2) If primary fails => return fallback (source=fallback_error).
      3) If primary succeeds but exceeds latency budget => return fallback (source=fallback_latency_budget).
      4) Otherwise => return primary (source=primary).
    """
    payload = {"prompt": req.prompt}

    # 1) Call primary
    primary = llm.call(payload)

    # 2) On failure, serve fallback
    if not primary["ok"]:
        meta = primary.get("meta", {})
        err = primary.get("error", "unknown_error")
        fb = call_fallback(payload)
        return GenerateResponse(
            text=fb["text"],
            meta=_mk_meta("fallback_error", {"primary_error": err, "primary_meta": meta}),
        )

    # 3) If primary is slow (over latency budget), prefer fallback
    meta = primary["meta"]
    if llm.latency_budget_exceeded(meta):
        fb = call_fallback(payload)
        return GenerateResponse(
            text=fb["text"],
            meta=_mk_meta("fallback_latency_budget", {"primary_meta": meta}),
        )

    # 4) Normal success path
    return GenerateResponse(
        text=primary["result"]["text"],
        meta=_mk_meta("primary", meta),
    )
