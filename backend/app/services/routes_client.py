"""Google Routes API (computeRouteMatrix): real travel minutes between a day's places.

Request-time data only: the minutes go into this request's travel table and are never stored
(Google terms decision 2026-11-16). A pair Google cannot route (no transit, bad coordinates,
failed batch) is simply missing from the result; the caller fills it with an estimate.
"""

import os
from datetime import datetime
from math import ceil
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from app.schemas.enums import TravelMode
from app.schemas.models import TravelTime

_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
TIMEOUT_SECONDS = 10.0
STEP = 5
FIELDS = "originIndex,destinationIndex,duration,condition"

GOOGLE_MODE = {TravelMode.TRANSIT: "TRANSIT", TravelMode.WALK: "WALK", TravelMode.CAR: "DRIVE"}
# Google's per-request cap on origins x destinations (transit is the strict one).
MAX_ELEMENTS = {TravelMode.TRANSIT: 100, TravelMode.WALK: 625, TravelMode.CAR: 625}


def routes_enabled() -> bool:
    """Real travel times are OFF unless ROUTES_TRAVEL_ENABLED is 1/true (decision 2026-11-25).

    Google's matrix method needs a billing account, so without one every call is refused and
    only adds delay before the estimate. A key in .env does not turn it on by itself."""
    load_dotenv(_ENV_PATH)
    return os.environ.get("ROUTES_TRAVEL_ENABLED", "").strip().lower() in {"1", "true"}


class RoutesError(RuntimeError):
    """Google could not answer (network, quota, bad key). The message never contains the key."""


class RoutesConfigError(RoutesError):
    """GOOGLE_ROUTES_API_KEY missing."""


def _waypoint(point: tuple[float, float]) -> dict[str, Any]:
    return {"waypoint": {"location": {"latLng": {"latitude": point[0], "longitude": point[1]}}}}


def _seconds(duration: str) -> int:
    """Google sends durations as "1234s"."""
    return int(float(duration.removesuffix("s")))


def _round_up(seconds: int) -> int:
    return max(STEP, ceil(seconds / 60 / STEP) * STEP)


class GoogleRoutesClient:
    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None) -> None:
        load_dotenv(_ENV_PATH)
        key = (api_key or os.environ.get("GOOGLE_ROUTES_API_KEY", "")).strip()
        if not key:
            raise RoutesConfigError("GOOGLE_ROUTES_API_KEY is not set (see .env)")
        self._key = key
        self._http = client or httpx.Client(timeout=TIMEOUT_SECONDS)

    def _post(self, body: dict[str, Any]) -> list[dict[str, Any]]:
        headers = {"X-Goog-Api-Key": self._key, "X-Goog-FieldMask": FIELDS}
        try:
            response = self._http.post(URL, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise RoutesError(f"Routes request failed: {type(exc).__name__}") from exc
        if response.status_code != 200:
            try:
                detail = response.json()[0]["error"]["message"]
            except (ValueError, LookupError, TypeError):
                detail = ""
            raise RoutesError(f"Routes returned HTTP {response.status_code}: {detail[:200]}")
        return response.json()

    def matrix(
        self,
        points: dict[str, tuple[float, float]],
        mode: TravelMode,
        depart_at: datetime | None = None,
    ) -> tuple[TravelTime, ...]:
        """Minutes for every pair Google can route, as undirected TravelTime(source="api").

        A -> B and B -> A can differ (one-way streets, timetables); the table is undirected, so
        the longer one is kept: a plan that fits the slower direction fits both.
        `depart_at` must be timezone-aware (transit timetables depend on the day)."""
        ids = sorted(points)  # same input, same request, same order
        per_call = max(1, MAX_ELEMENTS[mode] // max(1, len(ids)))  # origins per request
        found: dict[frozenset[str], int] = {}
        for i in range(0, len(ids), per_call):
            chunk = ids[i : i + per_call]
            body: dict[str, Any] = {
                "origins": [_waypoint(points[k]) for k in chunk],
                "destinations": [_waypoint(points[k]) for k in ids],
                "travelMode": GOOGLE_MODE[mode],
            }
            if depart_at is not None:
                body["departureTime"] = depart_at.isoformat()
            for el in self._post(body):
                if el.get("condition") != "ROUTE_EXISTS" or "duration" not in el:
                    continue
                a, b = chunk[el["originIndex"]], ids[el["destinationIndex"]]
                if a == b:
                    continue
                key = frozenset((a, b))
                found[key] = max(found.get(key, 0), _round_up(_seconds(el["duration"])))
        return tuple(
            TravelTime(a=a, b=b, minutes=found[frozenset((a, b))], source="api")
            for n, a in enumerate(ids)
            for b in ids[n + 1 :]
            if frozenset((a, b)) in found
        )
