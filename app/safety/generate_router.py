# app/safety/generate_router.py
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.infra.llm_client import LLMClient
from app.providers.mock_llm import call_model as mock_call_model  # swap to real later

log = logging.getLogger("persona_lab.generate")
router = APIRouter(tags=["safety"])

# Single shared client instance
llm = LLMClient(fn_call_model=mock_call_model)


class GenerateRequest(BaseModel):
    prompt: str


class GenerateResponse(BaseModel):
    text: str
    meta: dict


@router.post("/generate_v2", response_model=GenerateResponse)
def safety_generate(req: GenerateRequest):
    """
    Milestone 9A — resilient generation:
      - per-call timeout
      - bounded retries (transient only)
      - circuit breaker with half-open probes
    """
    result = llm.call({"prompt": req.prompt})

    if not result["ok"]:
        meta = result.get("meta", {})
        err = result.get("error", "unknown_error")
        # 9B will add graceful fallback; for now surface a clean 503.
        raise HTTPException(status_code=503, detail={"error": err, "meta": meta})

    meta = result["meta"]
    text = result["result"]["text"]
    return GenerateResponse(text=text, meta=meta)
