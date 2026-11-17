"""A day of the user's trip as the browser keeps it -> the pieces of an engine input.

The browser keeps only place_ids, times and tiers (Google terms decision 2026-11-16). The server
turns them into `Day`, `Activity`, `Preference` and the travel table for one request and keeps
nothing; the browser holds the result in memory while recovering.
"""

import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.enums import Category, Tier, TravelMode
from app.schemas.models import MINUTES_PER_DAY, Activity, Day, Preference, TravelTime, _Frozen


class PlanItem(_Frozen):
    id: str
    title: str  # the user's own words
    category: Category
    start: int = Field(ge=0, le=MINUTES_PER_DAY)
    end: int = Field(ge=0, le=MINUTES_PER_DAY)
    place_id: str
    tier: Tier
    reservation_time: int | None = Field(default=None, ge=0, le=MINUTES_PER_DAY)

    @model_validator(mode="after")
    def _check_range(self) -> "PlanItem":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class PlanRequest(_Frozen):
    date: datetime.date
    hotel_place_id: str
    end_deadline: int = Field(ge=0, le=MINUTES_PER_DAY)
    travel_mode: TravelMode = TravelMode.TRANSIT
    items: tuple[PlanItem, ...] = Field(min_length=1)


class PlanWarning(_Frozen):
    """Something the user should know before recovering. Never silently "fixed"."""

    code: Literal["CLOSED_THAT_DAY"]  # Google says the place is closed on the trip's weekday
    activity_id: str


class BuiltPlan(_Frozen):
    day: Day
    activities: tuple[Activity, ...]
    preferences: tuple[Preference, ...]
    travel: tuple[TravelTime, ...]
    warnings: tuple[PlanWarning, ...] = ()
