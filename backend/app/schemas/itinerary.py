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
    # lodging = something done at the traveler's own hotel; airport = an airport block that is
    # not the day's arrival or departure. Transport blocks never become items (see DraftLeg).
    role: Literal["activity", "lodging", "airport"] = "activity"
    start: int | None = Field(default=None, ge=0, le=MINUTES_PER_DAY)
    end: int | None = Field(default=None, ge=0, le=MINUTES_PER_DAY)
    # True when `end` was filled from the category default, not written by the user.
    duration_estimated: bool = False
    reservation_time: int | None = Field(default=None, ge=0, le=MINUTES_PER_DAY)
    note: str | None = None
    # Where the item is (step 2b). written: search `place_query` (+ `address`); venue: inside
    # item `place_of`, or, with no such item, search `place_query` (the larger place's name);
    # previous: same place as item `place_of`; hotel: the trip's hotel; none: the user picks
    # (never searched by the title).
    place_source: Literal["written", "venue", "previous", "hotel", "none"] = "none"
    place_of: int | None = Field(default=None, ge=0)
    # Place name to search with, written in the block itself.
    place_query: str | None = None
    address: str | None = None  # street address, as written in the pasted text
    spot: str | None = None  # the spot inside the larger place, as written ("판타지랜드")
    # Patch picture for the screen (worship, museum, ...). None = the category's picture.
    patch: PatchKind | None = None


class DraftLeg(_Frozen):
    """A transport block, kept as the way between two items, not as an item. `after` / `before`
    are item indexes; None = the day's start (hotel or arrival airport) / end."""

    after: int | None = Field(ge=0)
    before: int | None = Field(ge=0)
    start: int | None = Field(default=None, ge=0, le=MINUTES_PER_DAY)
    end: int | None = Field(default=None, ge=0, le=MINUTES_PER_DAY)
    title: str
    note: str | None = None


class DraftFlight(_Frozen):
    """Airport blocks at the start / end of a day, read as the arrival / departure flight.
    `time` is landing / take-off. `time_written` is False when the text gives no take-off and
    the last airport block's end stands in: the screen asks the user to check it."""

    airport_query: str | None
    time: int = Field(ge=0, le=MINUTES_PER_DAY)
    buffer_minutes: int | None = Field(ge=0, le=MINUTES_PER_DAY)
    time_written: bool
    absorbed: tuple[str, ...] = ()  # titles of the blocks this flight stands for


class DraftDay(_Frozen):
    day_label: str | None
    theme: str | None = None
    items: tuple[DraftItem, ...]
    legs: tuple[DraftLeg, ...] = ()
    arrival: DraftFlight | None = None
    departure: DraftFlight | None = None
    # When the text has the day end at the hotel (its trailing transport / lodging blocks end).
    # None = not written: the trip's default deadline applies.
    end_time: int | None = Field(default=None, ge=0, le=MINUTES_PER_DAY)
    issues: tuple[DraftIssue, ...] = ()


class DraftItinerary(_Frozen):
    # The traveler's hotel as written (the name lodging blocks use most). None = not written.
    hotel_query: str | None = None
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


class PartialRead(_Frozen):
    """The draft covers only part of the text, even after asking twice: `read` timed items came
    back for `written` time lines. The screen tells the user what is missing."""

    read: int = Field(ge=0)
    written: int = Field(ge=1)


class ParseResponse(_Frozen):
    status: Literal["ok", "manual"]
    draft: DraftItinerary | None  # set exactly when status is "ok"
    problem: ParseProblem | None = None
    partial: PartialRead | None = None  # None = the draft covers the text
