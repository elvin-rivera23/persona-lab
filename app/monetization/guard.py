import os
import threading
from datetime import UTC, datetime

from app.monetization.models import MonetizationPlan


class MonetizationGuard:
    """
    In-memory per-day request counter and plan-based caps.

    NOT for multi-process or multi-instance accuracy.
    Replace with Redis for real deployments.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._day_key = self._current_day_key()
        # usage[(day_key, client_id)] = count
        self._usage: dict[tuple[str, str], int] = {}

    @staticmethod
    def _current_day_key() -> str:
        now = datetime.now(UTC)
        return now.strftime("%Y-%m-%d")  # UTC day bucket

    def _rollover_if_needed(self):
        cur = self._current_day_key()
        if cur != self._day_key:
            # New UTC day; reset usage
            self._usage = {}
            self._day_key = cur

    @staticmethod
    def _cap_for_plan(plan: MonetizationPlan) -> int:
        if plan in (MonetizationPlan.PREMIUM, MonetizationPlan.INTERNAL):
            # For now, unlimited in experiments
            return 10_000_000
        # FREE tier from env
        return int(os.getenv("FREE_TIER_DAILY_REQUESTS", "50"))

    def check_and_increment(self, client_id: str, plan: MonetizationPlan) -> tuple[bool, int, int]:
        """
        Returns (allowed, usage_after, cap)
        - If allowed is False, caller should reject with monetization exit.
        """
        if os.getenv("MONETIZATION_ENABLED", "0") != "1":
            # Treat as unlimited if disabled
            return True, 0, 10_000_000

        with self._lock:
            self._rollover_if_needed()
            cap = self._cap_for_plan(plan)
            key = (self._day_key, client_id)
            current = self._usage.get(key, 0)
            if current >= cap:
                return False, current, cap
            new_val = current + 1
            self._usage[key] = new_val
            return True, new_val, cap

    def snapshot(self, client_id: str, plan: MonetizationPlan) -> tuple[int, int]:
        """
        Returns (usage_today, cap) without increment.
        """
        with self._lock:
            self._rollover_if_needed()
            cap = self._cap_for_plan(plan)
            key = (self._day_key, client_id)
            current = self._usage.get(key, 0)
            return current, cap
