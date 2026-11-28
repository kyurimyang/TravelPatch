"""Step ⑦: find places that could stand in for a closed activity, before the engine runs.

The engine can only choose among substitutes it is given (it never looks places up). Here the
service layer asks the LLM what kind of place it was, asks Google Places for such places near
it, keeps those not closed at that time, and adds them with estimated travel times. The engine
then picks the one that changes the day least, or none.

`build_substitutes` is the pure decision part; `add_substitutes` does the I/O around it.

Rain or a "실내 우선" wish also searches indoor places for outdoor pieces (2026-11-26): a hit
Google types as indoors is marked outdoor=False, so the engine may use it in the rain.
"""

import logging
from collections import Counter
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from app.llm.provider import LLMProvider
from app.llm.substitute_query import substitute_query
from app.schemas.enums import Wish
from app.schemas.events import ClosureEvent, WeatherEvent
from app.schemas.models import HOTEL_ID, START_ID, Activity, Substitute
from app.schemas.recovery import RecoveryInput
from app.services.opening_hours import hours_for_weekday
from app.services.place_kind import place_outdoor
from app.services.places_client import (
    GooglePlacesClient,
    PlaceCandidate,
    PlaceDetails,
    PlacesError,
)
from app.services.travel_estimate import fill_missing_travel, haversine_km

log = logging.getLogger(__name__)

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


# Outdoor pieces searched for an indoor stand-in per request (one LLM call + one search each).
MAX_INDOOR_SEARCHES = 2


def _eat_drink(t: str) -> bool:
    return t in EAT_DRINK_TYPES or t.endswith(EAT_DRINK_SUFFIXES)


def _same_kind(category: str, types: tuple[str, ...]) -> bool:
    if not types:  # Google gave no types: nothing to judge by
        return True
    if "lodging" in types:  # a hotel stands in for nothing in a day plan
        return False
    if category in ("meal", "cafe"):
        return any(_eat_drink(t) for t in types)
    # A sight or a shop is not stood in for by a place whose main kind (Google's first type) is a
    # restaurant or cafe: the Louvre was swapped for a cafe for 2.5 hours (user test 2026-11-27).
    return not _eat_drink(types[0])


@dataclass(frozen=True)
class Found:
    substitutes: tuple[Substitute, ...]
    # Substitutes whose hours that day are unknown: if the plan uses one, it gets needs_check.
    unknown_hours: frozenset[str]
    # Hits left out and why, sorted by reason: ("closed", 2), ("other_kind", 1), ... So a drop
    # can say "found 3, all closed then" instead of nothing (user test 2026-11-28).
    skipped: tuple[tuple[str, int], ...] = ()


def build_substitutes(
    target: Activity,
    places: Iterable[tuple[PlaceCandidate, PlaceDetails]],
    weekday: int | None,
    others: Iterable[tuple[float, float]] = (),
) -> Found:
    """Pure. `places` = (search hit, its details) in Google's order. `weekday` is Monday=0..Sunday=6,
    or None when the date is unknown (then every candidate's hours are unknown). `others` = where
    the day's other pieces are: a hit at one of them is not a stand-in (it would be the same place
    twice in a day: 경복궁 -> 북촌 한옥마을 already at 12:30, user test 2026-11-27).

    Keeps Google's order for ids (sub_<activity>_<n>), so the same answers give the same input.
    """
    taken = tuple(others)
    subs: list[Substitute] = []
    unknown: set[str] = set()
    skipped: Counter[str] = Counter()
    for hit, p in places:
        if not _same_kind(target.category, hit.types):
            skipped["other_kind"] += 1
            continue
        km = haversine_km((target.lat, target.lng), (p.lat, p.lng))
        if km < SAME_PLACE_KM:
            skipped["same_place"] += 1
            continue
        if any(haversine_km(o, (p.lat, p.lng)) < SAME_PLACE_KM for o in taken):
            skipped["already_in_day"] += 1
            continue
        slot = (target.planned_start, target.planned_end)  # pick the opening window around it
        hours = hours_for_weekday(p.periods, weekday, prefer=slot) if weekday is not None else None
        if hours is not None and hours.status == "closed":
            skipped["closed"] += 1
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
                outdoor=place_outdoor(hit.types),
            )
        )
    return Found(tuple(subs), frozenset(unknown), tuple(sorted(skipped.items())))


def _without_substitutes(inp: RecoveryInput, ids: Iterable[str]) -> list[str]:
    has = {s.replaces for s in inp.substitutes}
    return [i for i in dict.fromkeys(ids) if i not in has]


def closed_targets(inp: RecoveryInput) -> list[str]:
    """Closed activities (any of the events) with no substitute yet, in event order."""
    return _without_substitutes(
        inp, (ev.activity_id for ev in inp.events if isinstance(ev, ClosureEvent))
    )


def indoor_targets(inp: RecoveryInput) -> list[str]:
    """With rain or the "실내 우선" wish: outdoor pieces still ahead with no substitute yet, the
    most valuable first (then by id), at most MAX_INDOOR_SEARCHES."""
    rain = any(isinstance(ev, WeatherEvent) for ev in inp.events)
    if not rain and Wish.INDOOR not in inp.wishes:
        return []
    weight = {p.activity_id: p.tier.weight for p in inp.preferences}
    here = inp.event.location_id
    outdoor = [
        a.id
        for a in inp.activities
        if a.outdoor is True and a.planned_end > inp.now and a.id != here
    ]
    todo = _without_substitutes(inp, outdoor)
    return sorted(todo, key=lambda i: (-weight[i], i))[:MAX_INDOOR_SEARCHES]


def wants_substitutes(inp: RecoveryInput) -> bool:
    """A closure with no substitute yet, or an outdoor piece to find an indoor stand-in for: the
    cases that call the LLM and Google. The router asks this too, to charge a guest only when
    the search happens."""
    return bool(closed_targets(inp) or indoor_targets(inp))


def add_substitutes(
    inp: RecoveryInput, provider: LLMProvider, places: GooglePlacesClient
) -> RecoveryInput:
    """The input with substitutes for closed activities and (rain, "실내 우선") indoor ones for
    outdoor pieces, or unchanged when there is nothing to do or Google cannot answer (then the
    blockers say so). A substitute with unknown hours has no open_at/close_at; see
    `needs_check_ids`.
    """
    closed, indoor = closed_targets(inp), indoor_targets(inp)
    if not closed and not indoor:
        return inp
    # A closed outdoor piece in the rain is in both lists: one search (an indoor one), not two
    # with clashing ids (live test 2026-11-27, "타워 브리지 공사 + 비" -> 500).
    return add_substitutes_for(inp, [*closed, *indoor], provider, places, indoor=frozenset(indoor))


def add_substitutes_for(
    inp: RecoveryInput,
    ids: Iterable[str],
    provider: LLMProvider,
    places: GooglePlacesClient,
    indoor: frozenset[str] = frozenset(),
) -> RecoveryInput:
    """Substitutes for the given activities (decision 2026-11-23: also for pieces a plan drops,
    not only for a closure): "instead of dropping it, a similar place nearby that fits". The
    engine still decides; it takes a substitute only when that changes the day less than the drop.
    Unchanged when nothing was found."""
    targets: list[Activity] = []
    for aid in dict.fromkeys(ids):  # each activity searched once
        target = next((a for a in inp.activities if a.id == aid), None)
        if target is None or any(s.replaces == aid for s in inp.substitutes):
            continue
        targets.append(target)
    # Each search waits on the network (LLM, then Google), so run them side by side. `map` keeps
    # the order of `targets`, so the same input still gives the same substitutes and ids.
    found_all: list[Substitute] = []
    if targets:  # a pool needs at least one worker
        with ThreadPoolExecutor(max_workers=len(targets)) as pool:
            results = pool.map(lambda t: _search(inp, t, provider, places, t.id in indoor), targets)
            found_all = [sub for found in results for sub in found]
    if not found_all:
        return inp
    points = {a.id: (a.lat, a.lng) for a in inp.activities}
    points[HOTEL_ID] = (inp.day.end_lat, inp.day.end_lng)
    if inp.day.start_lat is not None and inp.day.start_lng is not None:
        points[START_ID] = (inp.day.start_lat, inp.day.start_lng)
    points.update({s.id: (s.lat, s.lng) for s in (*inp.substitutes, *found_all)})
    travel = fill_missing_travel(points, inp.travel, inp.day.travel_mode)
    data = inp.model_dump()
    data["substitutes"] = [s.model_dump() for s in (*inp.substitutes, *found_all)]
    data["travel"] = [t.model_dump() for t in travel]
    return RecoveryInput.model_validate(data)


def _search(
    inp: RecoveryInput,
    target: Activity,
    provider: LLMProvider,
    places: GooglePlacesClient,
    indoor: bool = False,
) -> list[Substitute]:
    """Places like `target` near it, open that day: one LLM call for what to search, one Google
    search that brings the hours along (no details call per hit). [] when Google cannot answer.
    `indoor`: an inside place is wanted (rain or the wish), so the search asks for one."""
    query = substitute_query(provider, target.title, target.category, indoor=indoor)
    try:
        details = places.search_with_hours(query, near=(target.lat, target.lng))
    except PlacesError as exc:  # the message never holds the key (see PlacesError)
        log.warning("substitute search failed for %s (%r): %s", target.id, query, exc)
        return []

    weekday = inp.day.date.weekday() if inp.day.date is not None else None
    # The day's other pieces, and where it starts and ends (the hotel is no stand-in for a sight).
    others = [(a.lat, a.lng) for a in inp.activities if a.id != target.id]
    others.append((inp.day.end_lat, inp.day.end_lng))
    if inp.day.start_lat is not None and inp.day.start_lng is not None:
        others.append((inp.day.start_lat, inp.day.start_lng))
    found = build_substitutes(target, details, weekday, others)
    # Nothing usable is what turns a closure into a plain drop: loud enough to show by default.
    level = logging.INFO if found.substitutes else logging.WARNING
    log.log(
        level,
        "substitute search for %s (%r): %d hits, %d kept, skipped %s",
        target.id,
        query,
        len(details),
        len(found.substitutes),
        dict(found.skipped) or "none",
    )
    return list(found.substitutes)


def needs_check_ids(inp: RecoveryInput) -> frozenset[str]:
    """Substitutes whose hours that day are unknown (no window at all): a plan that goes there
    must tell the user to check on site (invariant 8). Hand-made fixtures always carry hours."""
    return frozenset(s.id for s in inp.substitutes if s.open_at is None and s.close_at is None)
