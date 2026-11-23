"""Daily limits on the paid calls (LLM, Google Places) (decisions 2026-11-22, 2026-11-23).

Three limits per kind:
- per guest IP, so one guest cannot use up the day;
- for all guests together, because an IP header can be forged: whatever a caller does, the
  day's spend on guests stays under a known ceiling;
- per signed-in user. Sign-up needs no e-mail check, so "signed in" alone is no proof of a
  real person: without this, a script making accounts would spend without limit.

Where the counts live: the `usage_daily` table through charge_usage() (migration 0006) when
QUOTA_STORE=supabase, with guest IPs stored only as keyed hashes and kept for two days, so a restart (the free host sleeps after 15 idle minutes) or a second
instance does not start everyone from zero. Otherwise, or while the database cannot be
reached, in this process's memory: the limits still hold, only per process.
"""

import hashlib
import hmac
import logging
import os
import threading
from collections import Counter
from collections.abc import Callable
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict

log = logging.getLogger(__name__)


class Kind(StrEnum):
    LLM = "llm"
    PLACES = "places"


class Limit(BaseModel):
    model_config = ConfigDict(frozen=True)

    per_ip: int
    total: int
    per_user: int = 0  # 0 = use DEFAULT_PER_USER for the kind


# Draft values, to be tuned once real use is seen. A signed-in user gets a few times a guest's
# share: enough for several trips a day, bounded all the same.
DEFAULT_PER_USER: dict[Kind, int] = {Kind.LLM: 100, Kind.PLACES: 300}
LIMITS: dict[Kind, Limit] = {
    Kind.LLM: Limit(per_ip=20, total=300, per_user=DEFAULT_PER_USER[Kind.LLM]),
    Kind.PLACES: Limit(per_ip=60, total=1000, per_user=DEFAULT_PER_USER[Kind.PLACES]),
}

GUESTS = "guests"  # the subject that counts all guests together


def _utc_today() -> date:
    return datetime.now(UTC).date()


class UsageStore(Protocol):
    def charge(
        self, kind: Kind, subject: str, limit: int, total_subject: str | None, total_limit: int
    ) -> bool:
        """Count one call and say yes, or no without counting. Raises when it cannot tell."""
        ...


def pseudonymize(subject: str, secret: str) -> str:
    """A guest's IP is never written to the database as is: 'ip:' + a keyed hash (HMAC-SHA256,
    key known to the server only), enough to count one guest apart from another and nothing
    more. User ids stay as they are: withdrawal deletes their rows by id (services/account.py)."""
    if not subject.startswith("ip:"):
        return subject
    digest = hmac.new(secret.encode(), subject[3:].encode(), hashlib.sha256).hexdigest()
    return f"ip:{digest[:32]}"


class SupabaseUsageStore:
    """charge_usage() in Postgres: check and count in one transaction, so two servers (or two
    threads) can never both take the last call."""

    def __init__(self, client, secret: str) -> None:
        self._client = client
        self._secret = secret

    def charge(
        self, kind: Kind, subject: str, limit: int, total_subject: str | None, total_limit: int
    ) -> bool:
        res = self._client.rpc(
            "charge_usage",
            {
                "p_kind": kind.value,
                "p_subject": pseudonymize(subject, self._secret),
                "p_limit": limit,
                "p_total_subject": total_subject,
                "p_total_limit": total_limit,
            },
        ).execute()
        return bool(res.data)


class GuestQuota:
    def __init__(
        self,
        limits: dict[Kind, Limit] = LIMITS,
        today: Callable[[], date] = _utc_today,
        store: UsageStore | None = None,
    ) -> None:
        self._limits = limits
        self._today = today
        self._store = store
        self._lock = threading.Lock()  # sync routes run in worker threads
        self._day: date | None = None
        self._count: Counter[tuple[Kind, str]] = Counter()

    def charge(self, kind: Kind, ip: str) -> bool:
        """A guest's call. Called before the paid call, so a call that then fails still counts
        (retrying failures also costs money)."""
        limit = self._limits[kind]
        return self._charge(kind, f"ip:{ip}", limit.per_ip, GUESTS, limit.total)

    def charge_user(self, kind: Kind, user_id: str) -> bool:
        """A signed-in user's call: their own daily limit, apart from the guests' total."""
        limit = self._limits[kind]
        return self._charge(
            kind, f"user:{user_id}", limit.per_user or DEFAULT_PER_USER[kind], None, 0
        )

    def _charge(
        self, kind: Kind, subject: str, limit: int, total_subject: str | None, total_limit: int
    ) -> bool:
        if self._store is not None:
            try:
                return self._store.charge(kind, subject, limit, total_subject, total_limit)
            except Exception:  # database down: count here rather than refuse everyone
                log.warning("usage store unreachable, counting in memory", exc_info=True)
        with self._lock:
            day = self._today()
            if day != self._day:  # a new day (UTC midnight): everyone starts again
                self._day = day
                self._count.clear()
            if self._count[kind, subject] >= limit:
                return False
            if total_subject is not None and self._count[kind, total_subject] >= total_limit:
                return False
            self._count[kind, subject] += 1
            if total_subject is not None:
                self._count[kind, total_subject] += 1
            return True


def store_from_env() -> UsageStore | None:
    """The database store when QUOTA_STORE=supabase (set on the host, render.yaml). Off by
    default, so tests and local runs never write counts into a real project."""
    if os.environ.get("QUOTA_STORE", "").strip().lower() != "supabase":
        return None
    from app.db.client import get_client  # only imported when used: tests need no keys

    client = get_client()
    # The IP hash key: QUOTA_SECRET if set, else the service key, which the server has anyway
    # and which never leaves it.
    secret = os.environ.get("QUOTA_SECRET", "").strip() or os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return SupabaseUsageStore(client, secret)
