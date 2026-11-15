from typing import Literal

from pydantic import Field

from app.schemas.models import MINUTES_PER_DAY, _Frozen

IssueCode = Literal[
    "BAD_TIME",  # a time that is not "HH:MM"
    "BAD_RANGE",  # end is not after start
    "NO_TIME",  # no time at all: the user must give one
    "MISSING_START",  # only an end time: cannot place it
    "RESERVED_NO_TIME",  # marked as reserved but no start time to hold
    "OVER_MIDNIGHT",  # estimated end falls after midnight
    "OUT_OF_ORDER",  # starts before the item above it
    "OVERLAP",  # starts before the item above it ends
]


class DraftIssue(_Frozen):
    """Something the user should look at. `item` is the index in the day's item list."""

    code: IssueCode
    item: int = Field(ge=0)
    detail: str


class DraftItem(_Frozen):
    title: str
    category: Literal["meal", "sightseeing", "shopping", "cafe", "transport", "other"]
    start: int | None = Field(default=None, ge=0, le=MINUTES_PER_DAY)
    end: int | None = Field(default=None, ge=0, le=MINUTES_PER_DAY)
    # True when `end` was filled from the category default, not written by the user.
    duration_estimated: bool = False
    reservation_time: int | None = Field(default=None, ge=0, le=MINUTES_PER_DAY)
    note: str | None = None


class DraftDay(_Frozen):
    day_label: str | None
    items: tuple[DraftItem, ...]
    issues: tuple[DraftIssue, ...] = ()


class DraftItinerary(_Frozen):
    days: tuple[DraftDay, ...]
