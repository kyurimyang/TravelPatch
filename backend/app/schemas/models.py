from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.enums import Category, Tier, TimeRigidity

# All times are minutes since midnight (int). 09:30 -> 570.
MINUTES_PER_DAY = 1440


# Location id of the hotel in travel tables (start of day and the return deadline).
HOTEL_ID = "hotel"


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


class Preference(_Frozen):
    activity_id: str
    tier: Tier
    substitutability: float = Field(ge=0.0, le=1.0)
    time_rigidity: TimeRigidity


class Day(_Frozen):
    id: str
    timezone: str = "Asia/Tokyo"
    start_time: int = Field(ge=0, le=MINUTES_PER_DAY)
    end_deadline: int = Field(ge=0, le=MINUTES_PER_DAY)
    end_lat: float
    end_lng: float
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _check_window(self) -> "Day":
        if self.end_deadline <= self.start_time:
            raise ValueError("end_deadline must be after start_time")
        return self
