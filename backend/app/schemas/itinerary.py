from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.llm.parser import MAX_TEXT_CHARS, PatchKind
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
    # Place name to search with, written in the line itself. None = search by the title.
    place_query: str | None = None
    # Patch picture for the screen (worship, museum, ...). None = the category's picture.
    patch: PatchKind | None = None


class DraftDay(_Frozen):
    day_label: str | None
    items: tuple[DraftItem, ...]
    issues: tuple[DraftIssue, ...] = ()


class DraftItinerary(_Frozen):
    days: tuple[DraftDay, ...]


class ParseRequest(_Frozen):
    # Stripped first, so whitespace-only text is refused before any LLM call.
    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEXT_CHARS)
    ]


class ParseProblem(_Frozen):
    """Why no draft came back. The screen then offers manual entry instead of an error."""

    code: Literal[
        "LLM_FAILED",  # the model gave no usable answer twice
        "NOTHING_FOUND",  # the model read no item at all from the text
    ]
    detail: str


class ParseResponse(_Frozen):
    status: Literal["ok", "manual"]
    draft: DraftItinerary | None  # set exactly when status is "ok"
    problem: ParseProblem | None = None
