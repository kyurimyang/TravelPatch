"""Read/write access to the `places` cache. No Google calls here: those sit on top of this.

Only what Google's policy lets us keep is stored: the place_id, and its coordinates for at
most 30 days (we use 29, a day of margin). A row whose coordinates expired counts as
missing, so callers fetch it again. Times come from the `now` argument, defaulting to the
real clock only at this I/O boundary.
"""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from supabase import Client

from app.schemas.place import Place

TABLE = "places"
COORD_TTL = timedelta(days=29)


def _now(now: datetime | None) -> datetime:
    return now if now is not None else datetime.now(UTC)


def is_fresh(place: Place, now: datetime) -> bool:
    return (
        place.lat is not None
        and place.lng is not None
        and place.fetched_at is not None
        and now - place.fetched_at < COORD_TTL
    )


def get_places(
    client: Client, place_ids: Iterable[str], now: datetime | None = None
) -> dict[str, Place]:
    """Cached places with usable coordinates. Unknown or expired ids are absent."""
    ids = sorted(set(place_ids))
    if not ids:
        return {}
    at = _now(now)
    rows = client.table(TABLE).select("*").in_("place_id", ids).execute().data
    places = (Place.model_validate(row) for row in rows)
    return {p.place_id: p for p in places if is_fresh(p, at)}


def missing_ids(cached: dict[str, Place], wanted: Iterable[str]) -> list[str]:
    """Ids still to fetch from Google, in sorted order so the call is deterministic."""
    return sorted(set(wanted) - cached.keys())


def save_places(client: Client, places: Iterable[Place], now: datetime | None = None) -> None:
    """Insert or refresh places. `fetched_at` is stamped here and restarts the 30-day limit."""
    stamp = _now(now).isoformat()
    rows = [
        {**p.model_dump(mode="json", exclude={"fetched_at"}), "fetched_at": stamp}
        for p in sorted(places, key=lambda p: p.place_id)
    ]
    if rows:
        client.table(TABLE).upsert(rows, on_conflict="place_id").execute()


def purge_expired(client: Client, now: datetime | None = None) -> None:
    """Null the coordinates of rows older than the limit. The place_id row itself stays."""
    cutoff = (_now(now) - COORD_TTL).isoformat()
    client.table(TABLE).update({"lat": None, "lng": None}).lt("fetched_at", cutoff).execute()
