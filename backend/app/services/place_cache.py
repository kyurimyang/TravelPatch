"""Read/write access to the `places` cache. No Google calls here: those sit on top of this.

Cache first (CLAUDE.md 11): callers ask the cache, and only fetch from Google for the ids
that come back missing.
"""

from collections.abc import Iterable
from datetime import UTC, datetime

from supabase import Client

from app.schemas.place import Place

TABLE = "places"


def get_places(client: Client, place_ids: Iterable[str]) -> dict[str, Place]:
    """Cached places by id. Ids that are not cached are simply absent from the result."""
    ids = sorted(set(place_ids))
    if not ids:
        return {}
    rows = client.table(TABLE).select("*").in_("place_id", ids).execute().data
    return {row["place_id"]: Place.model_validate(row) for row in rows}


def missing_ids(cached: dict[str, Place], wanted: Iterable[str]) -> list[str]:
    """Ids still to fetch from Google, in sorted order so the call is deterministic."""
    return sorted(set(wanted) - cached.keys())


def save_places(client: Client, places: Iterable[Place]) -> None:
    """Insert or refresh places. `fetched_at` is stamped here, at the I/O boundary."""
    now = datetime.now(UTC).isoformat()
    rows = [
        {**p.model_dump(mode="json", exclude={"fetched_at"}), "fetched_at": now}
        for p in sorted(places, key=lambda p: p.place_id)
    ]
    if rows:
        client.table(TABLE).upsert(rows, on_conflict="place_id").execute()
