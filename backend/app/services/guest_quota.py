"""Daily limits on the paid calls (LLM, Google Places) for guests (decision 2026-11-22).

Signed-in users are not counted. Two limits per kind: one per IP, so one guest cannot use up
the day, and one for all guests together, because an IP header can be forged: whatever a
caller does, the day's spend on guests stays under a known ceiling.

Kept in memory: a restart or a second server instance starts from zero. Good enough for one
small instance; a shared store (Redis, a table) would be the next step.
"""

import threading
from collections import Counter
from collections.abc import Callable
from datetime import UTC, date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Kind(StrEnum):
    LLM = "llm"
    PLACES = "places"


class Limit(BaseModel):
    model_config = ConfigDict(frozen=True)

    per_ip: int
    total: int


# Draft values, to be tuned once real use is seen.
LIMITS: dict[Kind, Limit] = {
    Kind.LLM: Limit(per_ip=20, total=300),
    Kind.PLACES: Limit(per_ip=60, total=1000),
}


def _utc_today() -> date:
    return datetime.now(UTC).date()


class GuestQuota:
    def __init__(
        self, limits: dict[Kind, Limit] = LIMITS, today: Callable[[], date] = _utc_today
    ) -> None:
        self._limits = limits
        self._today = today
        self._lock = threading.Lock()  # sync routes run in worker threads
        self._day: date | None = None
        self._per_ip: Counter[tuple[Kind, str]] = Counter()
        self._total: Counter[Kind] = Counter()

    def charge(self, kind: Kind, ip: str) -> bool:
        """Count one call and say yes, or say no without counting. Called before the paid
        call, so a call that then fails still counts (retrying failures also costs money)."""
        limit = self._limits[kind]
        with self._lock:
            day = self._today()
            if day != self._day:  # a new day (UTC midnight): everyone starts again
                self._day = day
                self._per_ip.clear()
                self._total.clear()
            if self._per_ip[kind, ip] >= limit.per_ip or self._total[kind] >= limit.total:
                return False
            self._per_ip[kind, ip] += 1
            self._total[kind] += 1
            return True
