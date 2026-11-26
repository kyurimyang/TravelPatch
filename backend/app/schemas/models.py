import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.enums import Category, Tier, TimeRigidity, TravelMode

# All times are minutes since midnight (int). 09:30 -> 570.
MINUTES_PER_DAY = 1440
# Most activities one day may hold, for the recovery engine and the plan builder alike. The
# solver's work grows with every activity and is re-run per strategy and per reordering; a real
# day is far below this (the stress test runs 12).
MAX_ACTIVITIES = 16


# Location id of the hotel in travel tables (start of day and the return deadline).
# On a departure day the service layer puts the airport here: it is where the day must end.
HOTEL_ID = "hotel"
# Location id of where the day starts when that is not the hotel (an arrival airport). It exists
# only when the Day has start coordinates, and is only ever a current location, never a stop.
START_ID = "start"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TravelTime(_Frozen):
    # Undirected: the same minutes apply in both directions.
    a: str
    b: str
    minutes: int = Field(ge=0)
    source: Literal["api", "estimate"] = "estimate"


class Activity(_Frozen):
    id: str
    title: str
    category: Category
    lat: float
    lng: float
    planned_start: int = Field(ge=0, le=MINUTES_PER_DAY)
    planned_end: int = Field(ge=0, le=MINUTES_PER_DAY)
    min_duration: int = Field(gt=0)
    intent_tags: tuple[str, ...] = ()
    outdoor: bool | None = False  # None = unknown (never guess, CLAUDE.md rule 8)
    walking: bool | None = None  # lots of walking inside the activity; None = unknown
    open_at: int | None = Field(default=None, ge=0, le=MINUTES_PER_DAY)
    close_at: int | None = Field(default=None, ge=0, le=MINUTES_PER_DAY)
    reservation_time: int | None = Field(default=None, ge=0, le=MINUTES_PER_DAY)

    @property
    def ideal_duration(self) -> int:
        return self.planned_end - self.planned_start

    @model_validator(mode="after")
    def _check_durations(self) -> "Activity":
        if self.planned_end <= self.planned_start:
            raise ValueError("planned_end must be after planned_start")
        if self.min_duration > self.ideal_duration:
            raise ValueError("min_duration must not exceed the planned duration")
        return self


class Substitute(_Frozen):
    """A candidate place that can replace one activity (found upstream: LLM + Places check).

    The engine never looks places up; it only chooses among the candidates it is given.
    It keeps the replaced activity's tier and category, so it carries no tier of its own.
    """

    id: str  # a node of the travel table, like an activity id
    replaces: str  # id of the activity it can stand in for
    title: str
    lat: float
    lng: float
    duration: int = Field(gt=0)
    min_duration: int = Field(gt=0)
    open_at: int | None = Field(default=None, ge=0, le=MINUTES_PER_DAY)
    close_at: int | None = Field(default=None, ge=0, le=MINUTES_PER_DAY)
    penalty: float = Field(default=0.0, ge=0.0)  # new-place penalty added to D_sub
    # Whether the new place is outdoors. None: not known, read as the replaced activity's
    # (so an unknown place stands in for an outdoor one only when it is dry). Known indoor
    # places are how "rain, so somewhere inside instead" becomes a patch (2026-11-26).
    outdoor: bool | None = None

    @model_validator(mode="after")
    def _check_durations(self) -> "Substitute":
        if self.min_duration > self.duration:
            raise ValueError("min_duration must not exceed duration")
        return self


class Preference(_Frozen):
    activity_id: str
    tier: Tier
    substitutability: float = Field(ge=0.0, le=1.0)
    time_rigidity: TimeRigidity


class Day(_Frozen):
    id: str
    # The calendar day. The engine never reads it (it has no clock and no calendar); the service
    # layer uses it for the weekday of opening hours. None = unknown, e.g. old scenario files.
    date: datetime.date | None = None
    # Read by the service layer only, to estimate travel times. The engine never reads it.
    travel_mode: TravelMode = TravelMode.TRANSIT
    timezone: str = "Asia/Tokyo"
    start_time: int = Field(ge=0, le=MINUTES_PER_DAY)
    end_deadline: int = Field(ge=0, le=MINUTES_PER_DAY)
    end_lat: float
    end_lng: float
    # Where the day starts, when that is not the hotel (arrival airport). Both or neither.
    start_lat: float | None = None
    start_lng: float | None = None
    version: int = Field(default=1, ge=1)

    @property
    def has_start(self) -> bool:
        return self.start_lat is not None

    @model_validator(mode="after")
    def _check_window(self) -> "Day":
        if self.end_deadline <= self.start_time:
            raise ValueError("end_deadline must be after start_time")
        if (self.start_lat is None) != (self.start_lng is None):
            raise ValueError("give both start_lat and start_lng, or neither")
        return self
