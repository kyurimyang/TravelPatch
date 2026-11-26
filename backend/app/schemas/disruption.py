from typing import Literal

from pydantic import Field

from app.llm.disruption_interpreter import EventKind
from app.schemas.enums import Wish
from app.schemas.events import DisruptionEvent
from app.schemas.models import HOTEL_ID, MAX_ACTIVITIES, MINUTES_PER_DAY, Activity, _Frozen
from app.schemas.recovery import MAX_MORE_EVENTS

# One sentence plus what the user adds by tapping; more than this is not one moment's news.
MAX_ITEMS = MAX_MORE_EVENTS + 1


class EventDraft(_Frozen):
    """One event as heard, before the rules (services/event_builder.py). It starts as the LLM's
    reading and is what the client edits: answering a question or fixing a chip sets a field
    here and sends the drafts back to POST /disruptions/build (rules only, no LLM).

    Every field means "what the user said or chose"; none is ever shown as a name on screen.
    """

    type: EventKind
    delay_minutes: int | None = None
    time_from: str | None = None  # "HH:MM"
    time_to: str | None = None
    whole_day: bool | None = None
    activity_hint: str | None = None  # the user's words for a place in the plan
    activity_id: str | None = None  # the place the user picked from a question (wins over hint)
    extra_minutes: int | None = None
    wait_minutes: int | None = None
    new_time: str | None = None  # "HH:MM"
    shift_minutes: int | None = None  # reservation moved by this much; negative = earlier


class Question(_Frozen):
    """What to ask about one draft, in plain Korean. `field` says which draft field the answer
    fills (for the client's code, never displayed); `kind` says which control to show."""

    field: Literal[
        "type",
        "delay_minutes",
        "time_from",
        "activity_id",
        "extra_minutes",
        "wait_minutes",
        "new_time",
    ]
    kind: Literal["type", "minutes", "time", "place", "add_place"]
    text: str
    options: tuple[int, ...] = ()  # minutes to offer as chips (kind "minutes")
    candidates: tuple[str, ...] = ()  # activity ids to offer (kind "place")
    default: int | None = None  # minutes since midnight to prefill (kind "time")


class InterpretItem(_Frozen):
    """One event: built (with its chip), or waiting for an answer (with the question).
    A built event can still carry a question: how to correct it when the user taps the chip."""

    draft: EventDraft
    event: DisruptionEvent | None = None
    chip: str | None = None
    assumed: bool = False  # the chip shows a value a rule filled in ("지금부터"): check it
    question: Question | None = None


class WishChip(_Frozen):
    wish: Wish
    text: str


class InterpretRequest(_Frozen):
    text: str = Field(min_length=1, max_length=500)
    # "Now" and the user's place come from the client: the server never reads the clock here.
    now: int = Field(ge=0, le=MINUTES_PER_DAY)
    location_id: str = HOTEL_ID
    # Needed to match words like "저녁 식당" to an activity id (the LLM never sees the ids).
    activities: tuple[Activity, ...] = Field(max_length=MAX_ACTIVITIES)


class BuildRequest(_Frozen):
    """POST /disruptions/build: the rules again on edited drafts (no LLM, nothing charged)."""

    drafts: tuple[EventDraft, ...] = Field(max_length=MAX_ITEMS)
    wishes: tuple[Wish, ...] = Field(default=(), max_length=len(Wish))
    now: int = Field(ge=0, le=MINUTES_PER_DAY)
    location_id: str = HOTEL_ID
    activities: tuple[Activity, ...] = Field(max_length=MAX_ACTIVITIES)


class InterpretProblem(_Frozen):
    """Why the events are not all ready. `detail` is the question in plain Korean, never a
    field name (the screen shows it as is)."""

    code: Literal[
        "LLM_FAILED",  # the model gave no usable answer twice: the user picks the type
        "UNKNOWN_TYPE",
        "UNSUPPORTED",
        "MISSING_FIELD",
        "BAD_TIME",
        "NO_MATCH",
        "AMBIGUOUS",
    ]
    detail: str
    candidates: tuple[str, ...] = ()  # activity ids the user can choose from


class InterpretResponse(_Frozen):
    # "ok": every item has an event and nothing is waiting for an answer.
    status: Literal["ok", "needs_input"]
    event: DisruptionEvent | None  # the first built event (single-event clients use this)
    # Every built event in order: `event` first, the rest go to RecoveryInput.more_events.
    events: tuple[DisruptionEvent, ...] = ()
    items: tuple[InterpretItem, ...] = ()
    wishes: tuple[Wish, ...] = ()
    # Korean chip text filled from the events' own numbers (CLAUDE.md rule 5), events first,
    # then wishes, e.g. "지금(14:00)부터 비 · 하루 종일". Shown so the user can check.
    chips: tuple[str, ...] = ()
    # The wish chips again, with the wish each one stands for (so the screen can take one out).
    wish_chips: tuple[WishChip, ...] = ()
    problem: InterpretProblem | None = None  # the first open question, if any
