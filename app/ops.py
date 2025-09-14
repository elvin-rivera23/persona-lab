# app/ops.py
"""
Ops endpoints for liveness/readiness.

- /live  : returns 200 while process is alive (simple 'is process running?' check)
- /ready : returns 200 only after startup completed; flips to 503 during shutdown

Design:
- We rely on app.state.is_ready which is managed by the FastAPI lifespan context
  in app.main. That keeps readiness logic in one place and re-usable here.

What it does / Why needed / Pitfalls
- Provides K8s-ready probes without tying to any specific infra.
- Keeps liveness trivial and always-fast (no dependency checks).
- Readiness is a single boolean to start; you can expand it later (DB/cache checks).
- Pitfall: Don't perform heavy work in /live; it can get called very often.
"""

from fastapi import APIRouter, Request, Response, status

router = APIRouter(tags=["ops"])


@router.get("/live")
async def live() -> dict:
    # If the process is up enough to handle this request, we return 200.
    return {"status": "live"}


@router.get("/ready")
async def ready(request: Request):
    # Readiness is controlled by app.state.is_ready (set in lifespan).
    is_ready = getattr(request.app.state, "is_ready", False)
    if is_ready:
        return {"status": "ready"}
    # When not ready (startup not complete or shutdown in progress), return 503
    return Response(
        content='{"status":"not_ready"}',
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        media_type="application/json",
    )
