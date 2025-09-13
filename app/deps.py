import os

from fastapi import Request

from app.monetization.models import MonetizationPlan


def resolve_client(request: Request) -> tuple[str, MonetizationPlan]:
    """
    Resolve a (client_id, plan) tuple.
    - Prefer explicit X-Client-ID header.
    - Fallback to client IP (peername).
    - Plan can be hinted via X-Client-Plan when ALLOW_HEADER_PLANS=1.
    """
    headers = request.headers
    client_id = headers.get("X-Client-ID")
    if not client_id:
        # Fallback to peer IP (not perfect behind proxies; OK for demo)
        client_host = request.client.host if request.client else "unknown"
        client_id = f"ip:{client_host}"

    plan = MonetizationPlan.FREE
    if os.getenv("ALLOW_HEADER_PLANS", "0") == "1":
        raw = headers.get("X-Client-Plan", "").upper().strip()
        if raw in (p.value for p in MonetizationPlan):
            plan = MonetizationPlan(raw)

    return client_id, plan
