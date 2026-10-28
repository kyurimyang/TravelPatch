from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.schemas.enums import Category, EventType
from app.schemas.models import MINUTES_PER_DAY, _Frozen


class _EventBase(_Frozen):
    # "Now" as minutes since midnight. The engine never reads the clock itself.
    occurred_at: int = Field(ge=0, le=MINUTES_PER_DAY)


class DelayEvent(_EventBase):
    # Time the user can start moving again. "30 min late" is converted by the service layer.
    type: Literal[EventType.DELAY] = EventType.DELAY
    start_time: int = Field(ge=0, le=MINUTES_PER_DAY)

    @model_validator(mode="after")
    def _check_not_before_now(self) -> "DelayEvent":
        if self.start_time < self.occurred_at:
            raise ValueError("start_time must not be before occurred_at")
        return self


class WeatherEvent(_EventBase):
    type: Literal[EventType.WEATHER] = EventType.WEATHER
    start_time: int = Field(ge=0, le=MINUTES_PER_DAY)
    end_time: int | None = Field(default=None, ge=0, le=MINUTES_PER_DAY)


class ClosureEvent(_EventBase):
    type: Literal[EventType.CLOSURE] = EventType.CLOSURE
    activity_id: str


class FatigueEvent(_EventBase):
    type: Literal[EventType.FATIGUE] = EventType.FATIGUE
    max_walk_minutes: int = Field(gt=0)


class ExtendEvent(_EventBase):
    type: Literal[EventType.EXTEND] = EventType.EXTEND
    activity_id: str
    extra_minutes: int = Field(gt=0)


class ReservationChangeEvent(_EventBase):
    type: Literal[EventType.RESERVATION_CHANGE] = EventType.RESERVATION_CHANGE
    activity_id: str
    new_time: int = Field(ge=0, le=MINUTES_PER_DAY)


class MustVisitEvent(_EventBase):
    # A place not in the original plan that the user insists on visiting.
    # No planned_start/end: the engine decides where it goes.
    type: Literal[EventType.MUST_VISIT] = EventType.MUST_VISIT
    activity_id: str
    title: str
    category: Category
    lat: float
    lng: float
    duration: int = Field(gt=0)
    min_duration: int = Field(gt=0)
    open_at: int | None = Field(default=None, ge=0, le=MINUTES_PER_DAY)
    close_at: int | None = Field(default=None, ge=0, le=MINUTES_PER_DAY)

    @model_validator(mode="after")
    def _check_durations(self) -> "MustVisitEvent":
        if self.min_duration > self.duration:
            raise ValueError("min_duration must not exceed duration")
        return self


DisruptionEvent = Annotated[
    DelayEvent
    | WeatherEvent
    | ClosureEvent
    | FatigueEvent
    | ExtendEvent
    | ReservationChangeEvent
    | MustVisitEvent,
    Field(discriminator="type"),
]
