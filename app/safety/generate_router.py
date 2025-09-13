# app/safety/generate_router.py
from __future__ import annotations

import hashlib
import logging
from typing import Any

from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.infra.llm_client import LLMClient
from app.infra.ttl_cache import TTLCache
from app.providers.fallback_llm import call_fallback  # ultra-fast deterministic fallback
from app.providers.mock_llm import call_model as mock_call_model  # primary (swap to real later)

log = logging.getLogger("persona_lab.generate")
router = APIRouter(tags=["safety"])

# Shared instances
llm = LLMClient(fn_call_model=mock_call_model)
cache = TTLCache()


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
def safety_generate(
    req: GenerateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """
    Milestone 9B + 9C — Fallback + Lightweight Cache & Idempotency
      1) Derive stable cache key (Idempotency-Key header if present, else SHA-256 of prompt).
      2) Return cached response if present (source=cache_hit).
      3) Try primary via LLMClient (timeout + retries + circuit breaker).
      4) If primary fails => return fallback (source=fallback_error) and cache it.
      5) If primary succeeds but exceeds latency budget => return fallback (source=fallback_latency_budget) and cache it.
      6) Otherwise => return primary (source=primary) and cache it.
    """
    payload = {"prompt": req.prompt}

    # 1) Stable cache key
    if idempotency_key:
        key = f"idemp:{idempotency_key}"
    else:
        h = hashlib.sha256(req.prompt.encode("utf-8")).hexdigest()
        key = f"prompt:{h}"

    # 2) Cache lookup
    cached = cache.get(key)
    if cached:
        # IMPORTANT: don't let cached meta overwrite our "cache_hit" source
        return GenerateResponse(
            text=cached["text"],
            meta=_mk_meta("cache_hit", {"cached": cached["meta"]}),
        )

    # 3) Call primary
    primary = llm.call(payload)

    # 4) Failure => fallback (cache it)
    if not primary["ok"]:
        meta = primary.get("meta", {})
        err = primary.get("error", "unknown_error")
        fb = call_fallback(payload)
        result = {
            "text": fb["text"],
            "meta": _mk_meta("fallback_error", {"primary_error": err, "primary_meta": meta}),
        }
        cache.set(key, result)
        return GenerateResponse(text=result["text"], meta=result["meta"])

    # 5) Succeeded but over latency budget => fallback (cache it)
    meta = primary["meta"]
    if llm.latency_budget_exceeded(meta):
        fb = call_fallback(payload)
        result = {
            "text": fb["text"],
            "meta": _mk_meta("fallback_latency_budget", {"primary_meta": meta}),
        }
        cache.set(key, result)
        return GenerateResponse(text=result["text"], meta=result["meta"])

    # 6) Normal primary success (cache it)
    result = {"text": primary["result"]["text"], "meta": _mk_meta("primary", meta)}
    cache.set(key, result)
    return GenerateResponse(text=result["text"], meta=result["meta"])
