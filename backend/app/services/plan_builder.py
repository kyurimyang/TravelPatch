"""Step 5: one day of the user's trip (place_ids, times, tiers) -> the engine's input pieces.

Google gives coordinates and opening hours for this request only; nothing is stored (Google
terms decision 2026-11-16). Fields the pasted plan never had are filled by rule, the draft
values decided 2026-11-17, until the LLM suggestion step exists:
  min_duration     half the planned length, rounded down to 5 minutes, at least 15
  substitutability meal/cafe 0.6 (can eat elsewhere), others 0.2
  time_rigidity    reserved if there is a reservation, else flexible
  outdoor/walking  from Google's place types by rule (services/place_kind.py, 2026-11-27);
                   unknown (None) when the types do not settle it: never guessed (invariant 8)

Flights (decision 2026-11-18): an arrival starts the day at the airport (START_ID) once the
buffer has passed; a departure ends it at the airport (put in the HOTEL_ID node, "where the day
ends") a buffer before take-off. Items that no longer fit are warned about, never moved.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.schemas.enums import Category, TimeRigidity
from app.schemas.models import HOTEL_ID, START_ID, Activity, Day, Preference, TravelTime
from app.schemas.plan import BuiltPlan, PlanRequest, PlanWarning
from app.services.opening_hours import hours_for_weekday
from app.services.place_kind import place_outdoor, place_walking
from app.services.places_client import GooglePlacesClient, PlaceDetails
from app.services.routes_client import GoogleRoutesClient, RoutesError
from app.services.travel_estimate import fill_missing_travel

log = logging.getLogger(__name__)

STEP = 5
MIN_SHORTEST = 15
SUBSTITUTABLE = {Category.MEAL: 0.6, Category.CAFE: 0.6}
OTHER_SUBSTITUTABILITY = 0.2
DEFAULT_TIMEZONE = "Asia/Tokyo"  # only when Google gives no zone for the hotel or any place
MAX_PARALLEL = 8


def min_duration_for(planned: int) -> int:
    """Shortest acceptable visit: half the plan, rounded down to 5, at least 15 (never more than
    the plan itself)."""
    half = planned // 2 // STEP * STEP
    return min(planned, max(MIN_SHORTEST, half))


def _lookup(places: GooglePlacesClient, place_ids: list[str]) -> dict[str, PlaceDetails]:
    """Details for each distinct id, in parallel (each call waits on the network). Any failure
    raises: a day cannot be recovered without knowing where its places are."""
    unique = sorted(set(place_ids))
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
        found = list(pool.map(places.details, unique))
    return dict(zip(unique, found, strict=True))


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TIMEZONE)


def _real_travel(
    routes: GoogleRoutesClient | None,
    points: dict[str, tuple[float, float]],
    req: PlanRequest,
    first_start: int,
    zone: ZoneInfo,
    now: datetime,
) -> tuple[TravelTime, ...]:
    """Google's minutes for this day, or () when there is no client or Google fails: the
    caller fills every missing pair with an estimate, so a Routes outage never blocks a plan.

    One departure time serves the whole table: the day's first start. A time already past is
    left out (Google then uses "now")."""
    if routes is None:
        return ()
    depart = datetime.combine(req.date, datetime.min.time(), tzinfo=zone) + timedelta(
        minutes=first_start
    )
    try:
        return routes.matrix(points, req.travel_mode, depart if depart > now else None)
    except RoutesError:
        log.warning("Routes failed; using estimates for this plan", exc_info=True)
        return ()


def build_plan(
    req: PlanRequest,
    places: GooglePlacesClient,
    routes: GoogleRoutesClient | None = None,
    now: datetime | None = None,
) -> BuiltPlan:
    items = sorted(req.items, key=lambda it: (it.start, it.id))  # deterministic order
    airports = [f.airport_place_id for f in (req.arrival, req.departure) if f is not None]
    details = _lookup(places, [req.hotel_place_id, *airports, *(it.place_id for it in items)])
    weekday = req.date.weekday()

    activities: list[Activity] = []
    preferences: list[Preference] = []
    warnings: list[PlanWarning] = []
    for it in items:
        d = details[it.place_id]
        hours = hours_for_weekday(d.periods, weekday, prefer=(it.start, it.end))
        if hours.status == "closed":
            warnings.append(PlanWarning(code="CLOSED_THAT_DAY", activity_id=it.id))
        known = hours.status == "known"
        planned = it.end - it.start
        activities.append(
            Activity(
                id=it.id,
                title=it.title,
                category=it.category,
                lat=d.lat,
                lng=d.lng,
                planned_start=it.start,
                planned_end=it.end,
                min_duration=min_duration_for(planned),
                outdoor=place_outdoor(d.types),
                walking=place_walking(d.types, it.category),
                open_at=hours.open_at if known else None,
                close_at=hours.close_at if known else None,
                reservation_time=it.reservation_time,
            )
        )
        preferences.append(
            Preference(
                activity_id=it.id,
                tier=it.tier,
                substitutability=SUBSTITUTABLE.get(it.category, OTHER_SUBSTITUTABILITY),
                time_rigidity=(
                    TimeRigidity.RESERVED
                    if it.reservation_time is not None
                    else TimeRigidity.FLEXIBLE
                ),
            )
        )

    hotel = details[req.hotel_place_id]
    end = details[req.departure.airport_place_id] if req.departure else hotel
    start = details[req.arrival.airport_place_id] if req.arrival else None
    zone = hotel.time_zone or next(
        (details[it.place_id].time_zone for it in items if details[it.place_id].time_zone),
        DEFAULT_TIMEZONE,
    )
    points = {a.id: (a.lat, a.lng) for a in activities}
    points[HOTEL_ID] = (end.lat, end.lng)
    if start is not None:
        points[START_ID] = (start.lat, start.lng)
    known = _real_travel(routes, points, req, items[0].start, _zone(zone), now or datetime.now(UTC))
    travel = fill_missing_travel(points, known, mode=req.travel_mode)
    minutes = {frozenset((t.a, t.b)): t.minutes for t in travel}

    ready_at = req.ready_at
    if ready_at is None:
        to_first = minutes[frozenset((HOTEL_ID, activities[0].id))]
        start_time = max(0, activities[0].planned_start - to_first)
    else:
        start_time = ready_at
        warnings += [
            PlanWarning(code="BEFORE_ARRIVAL", activity_id=a.id)
            for a in activities
            if a.planned_start < ready_at + minutes[frozenset((START_ID, a.id))]
        ]
    if req.departure is not None:
        warnings += [
            PlanWarning(code="AFTER_DEPARTURE", activity_id=a.id)
            for a in activities
            if a.planned_end + minutes[frozenset((a.id, HOTEL_ID))] > req.deadline
        ]

    day = Day(
        id=req.date.isoformat(),
        date=req.date,
        timezone=zone,
        travel_mode=req.travel_mode,
        start_time=start_time,
        end_deadline=req.deadline,
        end_lat=end.lat,
        end_lng=end.lng,
        start_lat=start.lat if start else None,
        start_lng=start.lng if start else None,
    )
    return BuiltPlan(
        day=day,
        activities=tuple(activities),
        preferences=tuple(preferences),
        travel=travel,
        warnings=tuple(warnings),
    )
