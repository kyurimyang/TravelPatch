"""Google Places API (New) calls: search by text, details by place_id.

This is the only place that talks to Places. Everything Google returns is display or
request-time data: only `place_id` and the coordinates may go to the cache (see
`place_cache` and migration 0002). Names, addresses and opening hours are used for the
current request and dropped. Requests ask for the fields they need (field mask), which is
also what Google recommends to keep cost down.
"""

import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

# .env sits at the repo root, three levels above backend/app/services.
_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
BASE_URL = "https://places.googleapis.com/v1"
TIMEOUT_SECONDS = 10.0
MAX_CANDIDATES = 5
NEAR_RADIUS_M = 1500.0  # substitutes: about a 20-minute walk around the closed place

SEARCH_FIELDS = "places.id,places.displayName,places.formattedAddress,places.location,places.types"
# types: indoor/outdoor and walking by rule (services/place_kind.py), read per request, not stored.
DETAIL_FIELDS = "id,location,timeZone,regularOpeningHours.periods,types"


class PlacesError(RuntimeError):
    """Google could not answer (network, quota, bad key). The message never contains the key."""


class PlacesConfigError(PlacesError):
    """GOOGLE_PLACES_API_KEY missing."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class PlaceCandidate(_Frozen):
    """One search hit, for the user to pick from. Name and address are display only."""

    place_id: str
    name: str
    address: str | None
    lat: float
    lng: float
    types: tuple[str, ...] = ()  # Google place types, e.g. "japanese_izakaya_restaurant"


class OpeningPeriod(_Frozen):
    """Google's weekly period: days are 0=Sunday..6=Saturday, times are minutes since midnight.
    `close_*` None means open around the clock."""

    open_day: int
    open_minute: int
    close_day: int | None
    close_minute: int | None


class PlaceDetails(_Frozen):
    place_id: str
    lat: float
    lng: float
    time_zone: str | None
    # None = Google gave no hours: unknown, never "always open" (invariant 8).
    periods: tuple[OpeningPeriod, ...] | None
    types: tuple[str, ...] = ()  # Google place types, e.g. "park", "museum"


def _point(raw: dict[str, Any], key: str) -> tuple[int, int] | None:
    point = raw.get(key)
    if point is None:
        return None
    return int(point.get("day", 0)), int(point.get("hour", 0)) * 60 + int(point.get("minute", 0))


def _parse_periods(raw: dict[str, Any]) -> tuple[OpeningPeriod, ...] | None:
    periods = (raw.get("regularOpeningHours") or {}).get("periods")
    if not periods:
        return None
    out = []
    for p in periods:
        opened, closed = _point(p, "open"), _point(p, "close")
        if opened is None:
            continue
        out.append(
            OpeningPeriod(
                open_day=opened[0],
                open_minute=opened[1],
                close_day=closed[0] if closed else None,
                close_minute=closed[1] if closed else None,
            )
        )
    return tuple(out) or None


class GooglePlacesClient:
    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None) -> None:
        load_dotenv(_ENV_PATH)
        key = (api_key or os.environ.get("GOOGLE_PLACES_API_KEY", "")).strip()
        if not key:
            raise PlacesConfigError("GOOGLE_PLACES_API_KEY is not set (see .env)")
        self._key = key
        self._http = client or httpx.Client(timeout=TIMEOUT_SECONDS)

    def _call(self, method: str, url: str, fields: str, **kwargs: Any) -> dict[str, Any]:
        headers = {"X-Goog-Api-Key": self._key, "X-Goog-FieldMask": fields}
        try:
            response = self._http.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise PlacesError(f"Places request failed: {type(exc).__name__}") from exc
        if response.status_code != 200:
            try:
                detail = response.json().get("error", {}).get("message", "")
            except ValueError:
                detail = ""
            raise PlacesError(f"Places returned HTTP {response.status_code}: {detail[:200]}")
        return response.json()

    def search(
        self,
        query: str,
        language: str = "ko",
        near: tuple[float, float] | None = None,
        radius_m: float = NEAR_RADIUS_M,
    ) -> list[PlaceCandidate]:
        """Candidates for a place name, in Google's order. The caller (the user) picks one.

        `near` (lat, lng) prefers results around that point (a bias, not a hard limit)."""
        body: dict[str, Any] = {
            "textQuery": query,
            "languageCode": language,
            "maxResultCount": MAX_CANDIDATES,
        }
        if near is not None:
            center = {"latitude": near[0], "longitude": near[1]}
            body["locationBias"] = {"circle": {"center": center, "radius": radius_m}}
        data = self._call("POST", f"{BASE_URL}/places:searchText", SEARCH_FIELDS, json=body)
        return [
            PlaceCandidate(
                place_id=p["id"],
                name=(p.get("displayName") or {}).get("text", ""),
                address=p.get("formattedAddress"),
                lat=p["location"]["latitude"],
                lng=p["location"]["longitude"],
                types=tuple(p.get("types", ())),
            )
            for p in data.get("places", [])
            if "id" in p and "location" in p
        ]

    def details(self, place_id: str) -> PlaceDetails:
        data = self._call("GET", f"{BASE_URL}/places/{place_id}", DETAIL_FIELDS)
        return PlaceDetails(
            place_id=data["id"],
            lat=data["location"]["latitude"],
            lng=data["location"]["longitude"],
            time_zone=(data.get("timeZone") or {}).get("id"),
            periods=_parse_periods(data),
            types=tuple(data.get("types", ())),
        )
