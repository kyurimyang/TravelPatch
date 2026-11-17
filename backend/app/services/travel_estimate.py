"""Fallback travel times from coordinates, for pairs missing from the API cache.

Lives outside the engine on purpose: the engine only receives a finished travel table.
All constants are assumptions, to be replaced by cached Google Routes data where available.
"""

from dataclasses import dataclass
from itertools import combinations
from math import asin, ceil, cos, radians, sin, sqrt

from app.schemas.enums import TravelMode
from app.schemas.models import TravelTime

EARTH_RADIUS_KM = 6371.0088
STEP = 5


@dataclass(frozen=True)
class ModeParams:
    detour: float  # real routes are longer than the straight line
    speed_kmh: float  # door to door
    overhead_min: int  # waiting, transfers, parking, finding the entrance


# Draft values (decisions 2026-11-18). Transit keeps the numbers used before modes existed.
MODES: dict[TravelMode, ModeParams] = {
    TravelMode.TRANSIT: ModeParams(detour=1.3, speed_kmh=15.0, overhead_min=5),
    TravelMode.WALK: ModeParams(detour=1.3, speed_kmh=4.5, overhead_min=0),
    TravelMode.CAR: ModeParams(detour=1.4, speed_kmh=20.0, overhead_min=10),  # city traffic
}


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lng1, lat2, lng2 = map(radians, (*a, *b))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(h))


def _raw_minutes(km: float, p: ModeParams) -> float:
    return p.overhead_min + km * p.detour / p.speed_kmh * 60


def estimate_minutes(
    a: tuple[float, float], b: tuple[float, float], mode: TravelMode = TravelMode.TRANSIT
) -> int:
    """Minutes from a to b, rounded up to 5. A short hop is walked whatever the mode: nobody
    waits 10 minutes for a taxi to go 200 m."""
    km = haversine_km(a, b)
    raw = min(_raw_minutes(km, MODES[mode]), _raw_minutes(km, MODES[TravelMode.WALK]))
    return max(STEP, ceil(raw / STEP) * STEP)


def fill_missing_travel(
    points: dict[str, tuple[float, float]],
    known: tuple[TravelTime, ...] = (),
    mode: TravelMode = TravelMode.TRANSIT,
) -> tuple[TravelTime, ...]:
    """Known pairs are kept as given; every other pair gets an estimate (source="estimate")."""
    have = {frozenset((t.a, t.b)) for t in known}
    out = list(known)
    for a, b in combinations(sorted(points), 2):  # sorted: same input, same output order
        if frozenset((a, b)) not in have:
            out.append(
                TravelTime(
                    a=a,
                    b=b,
                    minutes=estimate_minutes(points[a], points[b], mode),
                    source="estimate",
                )
            )
    return tuple(out)
