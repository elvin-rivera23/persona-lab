from __future__ import annotations

from collections import Counter, deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime


@dataclass
class MonetizationEvent:
    ts: str
    client_id: str
    plan: str
    outcome: str  # e.g., "ALLOWED", "DENIED_CAP", "TEST"
    usage: int
    cap: int


class MonetizationMetrics:
    """
    Lightweight, in-memory counters + rolling log of monetization events.
    """

    def __init__(self, max_events: int = 200):
        self.plan_totals: Counter[str] = Counter()
        self.client_totals: Counter[str] = Counter()
        self.events: deque[MonetizationEvent] = deque(maxlen=max_events)

    def record(
        self,
        client_id: str,
        plan: str,
        outcome: str,
        usage: int,
        cap: int,
    ):
        self.plan_totals[plan] += 1
        self.client_totals[client_id] += 1
        evt = MonetizationEvent(
            ts=datetime.now(UTC).isoformat(),
            client_id=client_id,
            plan=plan,
            outcome=outcome,
            usage=usage,
            cap=cap,
        )
        self.events.append(evt)

    def snapshot(self) -> dict[str, object]:
        return {
            "plans": dict(self.plan_totals),
            "clients_top": self.client_totals.most_common(10),
            "recent": [asdict(e) for e in list(self.events)[-20:]],
        }


# Global singleton
metrics = MonetizationMetrics()
