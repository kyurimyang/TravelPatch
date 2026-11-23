"""MUST_VISIT, step before the engine: a place the user wants to add to the day (decision
2026-11-23) -> the event and the travel table with the new place in it.

The place comes from a Google pick (place_id), never from free text: coordinates and hours are
read for this request only and not stored (Google terms, 2026-11-16). Travel times to the new
place are estimates from coordinates, like every pair of a built day (plan_builder).
"""

from typing import Literal

from pydantic import Field

from app.schemas.enums import Category
from app.schemas.events import MustVisitEvent
from app.schemas.models import HOTEL_ID, MINUTES_PER_DAY, START_ID, TravelTime, _Frozen
from app.schemas.plan import BuiltPlan
from app.services.opening_hours import hours_for_weekday
from app.services.places_client import GooglePlacesClient
from app.services.plan_builder import min_duration_for
from app.services.travel_estimate import fill_missing_travel


class AddPlaceRequest(_Frozen):
    plan: BuiltPlan  # the day as Recover has it
    place_id: str = Field(min_length=1, max_length=300)
    title: str = Field(min_length=1, max_length=100)  # the user's words, shown on the patch
    category: Category = Category.SIGHTSEEING
    duration: int = Field(ge=15, le=300)  # minutes the user wants there
    now: int = Field(ge=0, le=MINUTES_PER_DAY)
    location_id: str = HOTEL_ID


class AddPlaceResponse(_Frozen):
    # "closed": Google says it is closed that day; the user is told instead of a patch that
    # cannot exist. "unknown" hours: added without a window, the patch says "check on site".
    hours: Literal["known", "closed", "unknown"]
    event: MustVisitEvent | None
    travel: tuple[TravelTime, ...]


def added_id(place_id: str, plan: BuiltPlan) -> str:
    taken = {a.id for a in plan.activities} | {HOTEL_ID, START_ID}
    base = f"add-{place_id[-12:]}"
    n, out = 1, base
    while out in taken:
        n += 1
        out = f"{base}-{n}"
    return out


def add_place(req: AddPlaceRequest, places: GooglePlacesClient) -> AddPlaceResponse:
    d = places.details(req.place_id)
    day = req.plan.day
    hours = (
        hours_for_weekday(d.periods, day.date.weekday())
        if day.date is not None
        else hours_for_weekday(None, 0)
    )
    if hours.status == "closed":
        return AddPlaceResponse(hours="closed", event=None, travel=req.plan.travel)
    new = added_id(req.place_id, req.plan)
    points = {a.id: (a.lat, a.lng) for a in req.plan.activities}
    points[HOTEL_ID] = (day.end_lat, day.end_lng)
    if day.start_lat is not None and day.start_lng is not None:
        points[START_ID] = (day.start_lat, day.start_lng)
    points[new] = (d.lat, d.lng)
    travel = fill_missing_travel(points, req.plan.travel, mode=day.travel_mode)
    event = MustVisitEvent(
        occurred_at=req.now,
        location_id=req.location_id,
        activity_id=new,
        title=req.title,
        category=req.category,
        lat=d.lat,
        lng=d.lng,
        duration=req.duration,
        min_duration=min_duration_for(req.duration),
        open_at=hours.open_at if hours.status == "known" else None,
        close_at=hours.close_at if hours.status == "known" else None,
    )
    return AddPlaceResponse(hours=hours.status, event=event, travel=travel)
