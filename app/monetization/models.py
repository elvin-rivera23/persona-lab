from enum import Enum

from pydantic import BaseModel, Field


class MonetizationPlan(str, Enum):
    FREE = "FREE"
    PREMIUM = "PREMIUM"
    INTERNAL = "INTERNAL"


class MonetizationStatus(BaseModel):
    client_id: str = Field(..., description="Resolved client identifier")
    plan: MonetizationPlan = Field(default=MonetizationPlan.FREE)
    usage_today: int = Field(
        ..., ge=0, description="Number of requests counted for the current UTC day"
    )
    daily_cap: int = Field(..., ge=0, description="Daily request cap for the resolved plan")
    remaining_today: int = Field(..., ge=0, description="Requests left before hitting the cap")
    as_of_utc: str = Field(..., description="Timestamp ISO-8601 in UTC")


class MonetizationConfig(BaseModel):
    enabled: bool
    free_tier_daily_requests: int
    allow_header_plans: bool
    notes: str | None = Field(default=None, description="Freeform notes for client UX")


class MonetizationExit(BaseModel):
    code: str = Field(..., description="Stable, machine-readable code")
    http_status: int = Field(..., description="HTTP status associated with this exit")
    summary: str = Field(..., description="Human short description")
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Canonical headers clients can expect (names only; values vary)",
    )
    retry_hint_utc: str | None = Field(
        default=None,
        description="If present, an ISO-8601 timestamp when client can retry without penalty",
    )


class MonetizationExitsDoc(BaseModel):
    exits: list[MonetizationExit]
    header_contract: dict[str, str] = Field(
        description="Header names and meanings used across monetization exits"
    )
    notes: str | None = None
