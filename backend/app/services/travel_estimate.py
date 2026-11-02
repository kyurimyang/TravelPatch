"""Fallback travel times from coordinates, for pairs missing from the API cache.

Lives outside the engine on purpose: the engine only receives a finished travel table.
All constants are assumptions, to be replaced by cached Google Routes data where available.
"""

from itertools import combinations
from math import asin, ceil, cos, radians, sin, sqrt

from app.schemas.models import TravelTime

EARTH_RADIUS_KM = 6371.0088
DETOUR_FACTOR = 1.3  # real routes are longer than the straight line
SPEED_KMH = 15.0  # walking + subway mix, door to door
OVERHEAD_MIN = 5  # waiting, transfers, finding the entrance
STEP = 5


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lng1, lat2, lng2 = map(radians, (*a, *b))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(h))


def estimate_minutes(a: tuple[float, float], b: tuple[float, float]) -> int:
    raw = OVERHEAD_MIN + haversine_km(a, b) * DETOUR_FACTOR / SPEED_KMH * 60
    return max(STEP, ceil(raw / STEP) * STEP)


def fill_missing_travel(
    points: dict[str, tuple[float, float]],
    known: tuple[TravelTime, ...] = (),
) -> tuple[TravelTime, ...]:
    """Known pairs are kept as given; every other pair gets an estimate (source="estimate")."""
    have = {frozenset((t.a, t.b)) for t in known}
    out = list(known)
    for a, b in combinations(sorted(points), 2):  # sorted: same input, same output order
        if frozenset((a, b)) not in have:
            out.append(
                TravelTime(a=a, b=b, minutes=estimate_minutes(points[a], points[b]), source="estimate")
            )
    return tuple(out)
