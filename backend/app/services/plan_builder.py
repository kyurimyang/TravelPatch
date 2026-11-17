"""Step 5: one day of the user's trip (place_ids, times, tiers) -> the engine's input pieces.

Google gives coordinates and opening hours for this request only; nothing is stored (Google
terms decision 2026-11-16). Fields the pasted plan never had are filled by rule, the draft
values decided 2026-11-17, until the LLM suggestion step exists:
  min_duration     half the planned length, rounded down to 5 minutes, at least 15
  substitutability meal/cafe 0.6 (can eat elsewhere), others 0.2
  time_rigidity    reserved if there is a reservation, else flexible
  outdoor/walking  unknown (None): never guessed (invariant 8)
"""

from concurrent.futures import ThreadPoolExecutor

from app.schemas.enums import Category, TimeRigidity
from app.schemas.models import HOTEL_ID, Activity, Day, Preference
from app.schemas.plan import BuiltPlan, PlanRequest, PlanWarning
from app.services.opening_hours import hours_for_weekday
from app.services.places_client import GooglePlacesClient, PlaceDetails
from app.services.travel_estimate import fill_missing_travel

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


def build_plan(req: PlanRequest, places: GooglePlacesClient) -> BuiltPlan:
    items = sorted(req.items, key=lambda it: (it.start, it.id))  # deterministic order
    details = _lookup(places, [req.hotel_place_id, *(it.place_id for it in items)])
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
                outdoor=None,
                walking=None,
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
    points = {a.id: (a.lat, a.lng) for a in activities}
    points[HOTEL_ID] = (hotel.lat, hotel.lng)
    travel = fill_missing_travel(points, mode=req.travel_mode)

    first = activities[0]
    to_first = next(t.minutes for t in travel if {t.a, t.b} == {HOTEL_ID, first.id})
    zone = hotel.time_zone or next(
        (details[it.place_id].time_zone for it in items if details[it.place_id].time_zone),
        DEFAULT_TIMEZONE,
    )
    day = Day(
        id=req.date.isoformat(),
        date=req.date,
        timezone=zone,
        travel_mode=req.travel_mode,
        start_time=max(0, first.planned_start - to_first),
        end_deadline=req.end_deadline,
        end_lat=hotel.lat,
        end_lng=hotel.lng,
    )
    return BuiltPlan(
        day=day,
        activities=tuple(activities),
        preferences=tuple(preferences),
        travel=travel,
        warnings=tuple(warnings),
    )
