# app/safety/generate_router.py
from __future__ import annotations

import hashlib
import logging
from typing import Any

from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.infra.llm_client import LLMClient
from app.infra.metrics import metrics  # NEW: observability
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
    9B + 9C + 9D — Fallback + Cache/Idempotency + Metrics
      1) Derive stable cache key (Idempotency-Key header if present, else SHA-256 of prompt).
      2) Return cached response if present (source=cache_hit) and record metrics.
      3) Try primary via LLMClient (timeout + retries + circuit breaker).
      4) If primary fails => return fallback and record metrics (source=fallback_error).
      5) If primary succeeds but exceeds latency budget => return fallback and record metrics (source=fallback_latency_budget).
      6) Otherwise => return primary and record metrics (source=primary).
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
        # Keep source explicit; nest original meta to avoid overwriting
        cached_meta = cached["meta"]
        # If we cached a primary/fallback result earlier, we can optionally propagate its latency
        cached_elapsed = None
        if isinstance(cached_meta, dict):
            orig = cached_meta.get("primary_meta") or cached_meta.get("cached") or cached_meta
            cached_elapsed = orig.get("elapsed_ms") if isinstance(orig, dict) else None
            cached_breaker = orig.get("breaker_state") if isinstance(orig, dict) else None
        else:
            cached_breaker = None
        metrics.record(
            "cache_hit", elapsed_ms=cached_elapsed, breaker_state=cached_breaker, attempts=None
        )
        return GenerateResponse(
            text=cached["text"], meta=_mk_meta("cache_hit", {"cached": cached_meta})
        )

    # 3) Call primary
    primary = llm.call(payload)

    # 4) Failure => fallback (cache it + metrics)
    if not primary["ok"]:
        meta = primary.get("meta", {})
        err = primary.get("error", "unknown_error")
        fb = call_fallback(payload)
        result = {
            "text": fb["text"],
            "meta": _mk_meta("fallback_error", {"primary_error": err, "primary_meta": meta}),
        }
        cache.set(key, result)
        metrics.record(
            "fallback_error",
            elapsed_ms=meta.get("elapsed_ms"),
            breaker_state=meta.get("breaker_state"),
            attempts=meta.get("attempts"),
        )
        return GenerateResponse(text=result["text"], meta=result["meta"])

    # 5) Succeeded but over latency budget => fallback (cache it + metrics)
    meta = primary["meta"]
    if llm.latency_budget_exceeded(meta):
        fb = call_fallback(payload)
        result = {
            "text": fb["text"],
            "meta": _mk_meta("fallback_latency_budget", {"primary_meta": meta}),
        }
        cache.set(key, result)
        metrics.record(
            "fallback_latency_budget",
            elapsed_ms=meta.get("elapsed_ms"),
            breaker_state=meta.get("breaker_state"),
            attempts=meta.get("attempts"),
        )
        return GenerateResponse(text=result["text"], meta=result["meta"])

    # 6) Normal primary success (cache it + metrics)
    result = {"text": primary["result"]["text"], "meta": _mk_meta("primary", meta)}
    cache.set(key, result)
    metrics.record(
        "primary",
        elapsed_ms=meta.get("elapsed_ms"),
        breaker_state=meta.get("breaker_state"),
        attempts=meta.get("attempts"),
    )
    return GenerateResponse(text=result["text"], meta=result["meta"])


@router.get("/inference_metrics")
def inference_metrics():
    """
    JSON metrics snapshot for dashboards/demos:
      - counters by outcome
      - breaker states seen
      - attempts histogram
      - latency p50/p95/max overall and by outcome
    """
    return metrics.snapshot()
