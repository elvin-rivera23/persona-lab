import os
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.deps import resolve_client
from app.monetization.guard import MonetizationGuard
from app.monetization.models import (
    MonetizationConfig,
    MonetizationExit,
    MonetizationExitsDoc,
    MonetizationPlan,
    MonetizationStatus,
)

router = APIRouter(prefix="/monetization", tags=["monetization"])

_guard = MonetizationGuard()

# Annotated dependency type for ruff B008 compliance
ResolvedClient = Annotated[tuple[str, MonetizationPlan], Depends(resolve_client)]


@router.get("/status", response_model=MonetizationStatus)
def get_status(request: Request, id_and_plan: ResolvedClient):
    client_id, plan = id_and_plan
    usage, cap = _guard.snapshot(client_id, plan)
    remaining = max(0, cap - usage)
    return MonetizationStatus(
        client_id=client_id,
        plan=plan,
        usage_today=usage,
        daily_cap=cap,
        remaining_today=remaining,
        as_of_utc=datetime.now(UTC).isoformat(),
    )


@router.get("/config", response_model=MonetizationConfig)
def get_config():
    return MonetizationConfig(
        enabled=(os.getenv("MONETIZATION_ENABLED", "0") == "1"),
        free_tier_daily_requests=int(os.getenv("FREE_TIER_DAILY_REQUESTS", "50")),
        allow_header_plans=(os.getenv("ALLOW_HEADER_PLANS", "0") == "1"),
        notes="Header-based plan selection is for experiments only. Do not use in production.",
    )


@router.get("/exits", response_model=MonetizationExitsDoc)
def get_exits_doc():
    """
    Documents the monetization exit taxonomy and the headers contract.
    Keep this in sync with enforcement points (e.g., /predict_ab).
    """
    exits = [
        MonetizationExit(
            code="MONETIZATION_CAP_EXCEEDED",
            http_status=429,
            summary="Daily request cap reached for your plan.",
            headers={
                "X-Monetization-Exit": "Machine-readable exit reason",
                "X-Monetization-Client": "Resolved client id used for metering",
                "X-Monetization-Plan": "Resolved plan (FREE|PREMIUM|INTERNAL)",
                "Retry-After": "Seconds until a generic retry is advisable",
            },
        ),
    ]
    header_contract = {
        "X-Monetization-Exit": "Stable exits like CAP_EXCEEDED",
        "X-Monetization-Client": "Echo of the metered client id",
        "X-Monetization-Plan": "Resolved plan at time of decision",
        "Retry-After": "Advisory seconds; true reset is next UTC midnight for FREE",
    }
    return MonetizationExitsDoc(
        exits=exits,
        header_contract=header_contract,
        notes="For production, replace header-plans with real auth and central storage (e.g., Redis).",
    )


@router.post("/test", response_model=MonetizationStatus)
def test_consume_one(request: Request, id_and_plan: ResolvedClient):
    """
    QA helper: consumes one unit from the guard for the resolved client/plan,
    then returns the updated status snapshot.
    """
    client_id, plan = id_and_plan
    _guard.check_and_increment(client_id, plan)
    usage, cap = _guard.snapshot(client_id, plan)
    return MonetizationStatus(
        client_id=client_id,
        plan=plan,
        usage_today=usage,
        daily_cap=cap,
        remaining_today=max(0, cap - usage),
        as_of_utc=datetime.now(UTC).isoformat(),
    )


def get_guard() -> MonetizationGuard:
    """
    For use in other routers to enforce caps:
    from app.monetization.router import get_guard
    allowed, used, cap = get_guard().check_and_increment(client_id, plan)
    """
    return _guard
