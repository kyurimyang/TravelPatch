"""Step ⑦: find places that could stand in for a closed activity, before the engine runs.

The engine can only choose among substitutes it is given (it never looks places up). Here the
service layer asks the LLM what kind of place it was, asks Google Places for such places near
it, keeps those not closed at that time, and adds them with estimated travel times. The engine
then picks the one that changes the day least, or none.

`build_substitutes` is the pure decision part; `add_substitutes` does the I/O around it.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from app.llm.provider import LLMProvider
from app.llm.substitute_query import substitute_query
from app.schemas.events import ClosureEvent
from app.schemas.models import HOTEL_ID, Activity, Substitute
from app.schemas.recovery import RecoveryInput
from app.services.opening_hours import hours_for_weekday
from app.services.places_client import (
    GooglePlacesClient,
    PlaceCandidate,
    PlaceDetails,
    PlacesError,
)
from app.services.travel_estimate import fill_missing_travel, haversine_km

SAME_PLACE_KM = 0.05  # a hit this close to the closed place is that place itself
# New-place penalty added to D_sub: a base for "not the place you chose" plus distance.
# Draft values (decisions 2026-11-18), same scale as the scenario C fixture (0.3 near, 0.6 far).
PENALTY_BASE = 0.2
PENALTY_PER_KM = 0.1
PENALTY_MAX = 1.0

# Google types that count as "a place to eat or drink". A text search near a closed izakaya can
# also return a cap shop on the same street; for meals and cafes those are left out.
EAT_DRINK_TYPES = {"restaurant", "food", "cafe", "coffee_shop", "bar", "pub", "bakery"}
EAT_DRINK_SUFFIXES = ("_restaurant", "_bar", "_cafe")


def _same_kind(category: str, types: tuple[str, ...]) -> bool:
    if category not in ("meal", "cafe") or not types:  # other kinds, or Google gave no types
        return True
    return any(t in EAT_DRINK_TYPES or t.endswith(EAT_DRINK_SUFFIXES) for t in types)


@dataclass(frozen=True)
class Found:
    substitutes: tuple[Substitute, ...]
    # Substitutes whose hours that day are unknown: if the plan uses one, it gets needs_check.
    unknown_hours: frozenset[str]


def build_substitutes(
    target: Activity, places: Iterable[tuple[PlaceCandidate, PlaceDetails]], weekday: int | None
) -> Found:
    """Pure. `places` = (search hit, its details) in Google's order. `weekday` is Monday=0..Sunday=6,
    or None when the date is unknown (then every candidate's hours are unknown).

    Keeps Google's order for ids (sub_<activity>_<n>), so the same answers give the same input.
    """
    subs: list[Substitute] = []
    unknown: set[str] = set()
    for hit, p in places:
        if not _same_kind(target.category, hit.types):
            continue
        km = haversine_km((target.lat, target.lng), (p.lat, p.lng))
        if km < SAME_PLACE_KM:
            continue
        slot = (target.planned_start, target.planned_end)  # pick the opening window around it
        hours = hours_for_weekday(p.periods, weekday, prefer=slot) if weekday is not None else None
        if hours is not None and hours.status == "closed":
            continue
        sub_id = f"sub_{target.id}_{len(subs) + 1}"
        known = hours is not None and hours.status == "known"
        if not known:
            unknown.add(sub_id)
        subs.append(
            Substitute(
                id=sub_id,
                replaces=target.id,
                title=hit.name or "대체 장소",
                lat=p.lat,
                lng=p.lng,
                duration=target.ideal_duration,
                min_duration=target.min_duration,
                open_at=hours.open_at if known else None,
                close_at=hours.close_at if known else None,
                penalty=round(min(PENALTY_MAX, PENALTY_BASE + PENALTY_PER_KM * km), 2),
            )
        )
    return Found(tuple(subs), frozenset(unknown))


def add_substitutes(
    inp: RecoveryInput, provider: LLMProvider, places: GooglePlacesClient
) -> RecoveryInput:
    """The input with substitutes for a closed activity, or unchanged when there is nothing to do
    (not a closure, substitutes already given) or Google cannot answer (then the blockers say so).
    A substitute with unknown hours has no open_at/close_at; see `needs_check_ids`.
    """
    ev = inp.event
    if not isinstance(ev, ClosureEvent) or any(
        s.replaces == ev.activity_id for s in inp.substitutes
    ):
        return inp
    target = next(a for a in inp.activities if a.id == ev.activity_id)

    query = substitute_query(provider, target.title, target.category)
    try:
        hits = places.search(query, near=(target.lat, target.lng))
    except PlacesError:
        return inp
    details: list[tuple[PlaceCandidate, PlaceDetails]] = []
    for hit in hits:
        try:
            details.append((hit, places.details(hit.place_id)))
        except PlacesError:
            continue  # one failed lookup only loses that candidate

    weekday = inp.day.date.weekday() if inp.day.date is not None else None
    found = build_substitutes(target, details, weekday)
    if not found.substitutes:
        return inp

    points = {a.id: (a.lat, a.lng) for a in inp.activities}
    points[HOTEL_ID] = (inp.day.end_lat, inp.day.end_lng)
    points.update({s.id: (s.lat, s.lng) for s in found.substitutes})
    travel = fill_missing_travel(points, inp.travel, inp.day.travel_mode)
    data = inp.model_dump()
    data["substitutes"] = [s.model_dump() for s in found.substitutes]
    data["travel"] = [t.model_dump() for t in travel]
    return RecoveryInput.model_validate(data)


def needs_check_ids(inp: RecoveryInput) -> frozenset[str]:
    """Substitutes whose hours that day are unknown (no window at all): a plan that goes there
    must tell the user to check on site (invariant 8). Hand-made fixtures always carry hours."""
    return frozenset(s.id for s in inp.substitutes if s.open_at is None and s.close_at is None)
