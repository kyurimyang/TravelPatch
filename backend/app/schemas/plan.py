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


# Default airport buffers in minutes (decision 2026-11-18). The user can change either per flight.
# Departure: airlines advise being at the airport 3 hours before an international flight
# (Delta, LATAM); check-in closes about 1 hour before (Korean Air). We take the advice, not the
# cut-off: a plan that misses the flight must never be offered.
DEPARTURE_BUFFER = 180
# Arrival: landing -> out of the airport (immigration, bags, customs). No official figure found;
# unofficial estimates for Tokyo are 30-70 minutes. 60 sits near the top of that range.
ARRIVAL_BUFFER = 60


class Flight(_Frozen):
    """A flight that bounds the day. `time` is local wall-clock minutes on the request's date:
    landing for an arrival, take-off for a departure. Entered by the user, never looked up."""

    time: int = Field(ge=0, le=MINUTES_PER_DAY)
    airport_place_id: str
    # None = the default for the flight's direction (ARRIVAL_BUFFER / DEPARTURE_BUFFER).
    buffer_minutes: int | None = Field(default=None, ge=0, le=360)


class PlanRequest(_Frozen):
    date: datetime.date
    hotel_place_id: str
    # Back-at-hotel deadline. On a departure day the flight sets the deadline instead, so it is
    # left out there; it is required on every other day.
    end_deadline: int | None = Field(default=None, ge=0, le=MINUTES_PER_DAY)
    travel_mode: TravelMode = TravelMode.TRANSIT
    items: tuple[PlanItem, ...] = Field(min_length=1)
    arrival: Flight | None = None  # the day starts at this airport after landing
    departure: Flight | None = None  # the day ends at this airport before take-off

    @property
    def ready_at(self) -> int | None:
        """When the user can leave the arrival airport. None = no arrival flight."""
        a = self.arrival
        if a is None:
            return None
        return a.time + (ARRIVAL_BUFFER if a.buffer_minutes is None else a.buffer_minutes)

    @property
    def deadline(self) -> int:
        """When the user must be at the day's end point: the airport on a departure day."""
        d = self.departure
        if d is None:
            assert self.end_deadline is not None  # guaranteed by _check_bounds
            return self.end_deadline
        return d.time - (DEPARTURE_BUFFER if d.buffer_minutes is None else d.buffer_minutes)

    @model_validator(mode="after")
    def _check_bounds(self) -> "PlanRequest":
        if self.departure is None and self.end_deadline is None:
            raise ValueError("end_deadline is required unless there is a departure flight")
        if self.departure is not None and self.end_deadline is not None:
            raise ValueError("give either end_deadline or a departure flight, not both")
        start = 0 if self.ready_at is None else self.ready_at
        if self.deadline <= start:
            raise ValueError("no time left between the arrival and the deadline")
        return self


class PlanWarning(_Frozen):
    """Something the user should know before recovering. Never silently "fixed"."""

    # CLOSED_THAT_DAY  Google says the place is closed on the trip's weekday
    # BEFORE_ARRIVAL   starts before the user can get there from the arrival airport
    # AFTER_DEPARTURE  ends too late to reach the departure airport in time
    code: Literal["CLOSED_THAT_DAY", "BEFORE_ARRIVAL", "AFTER_DEPARTURE"]
    activity_id: str


class BuiltPlan(_Frozen):
    day: Day
    activities: tuple[Activity, ...]
    preferences: tuple[Preference, ...]
    travel: tuple[TravelTime, ...]
    warnings: tuple[PlanWarning, ...] = ()
