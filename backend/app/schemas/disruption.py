from typing import Literal

from pydantic import Field

from app.llm.disruption_interpreter import InterpretedDisruption
from app.schemas.events import DisruptionEvent
from app.schemas.models import HOTEL_ID, MINUTES_PER_DAY, Activity, _Frozen


class InterpretRequest(_Frozen):
    text: str = Field(min_length=1, max_length=500)
    # "Now" and the user's place come from the client: the server never reads the clock here.
    now: int = Field(ge=0, le=MINUTES_PER_DAY)
    location_id: str = HOTEL_ID
    # Needed to match words like "저녁 식당" to an activity id (the LLM never sees the ids).
    activities: tuple[Activity, ...]


class InterpretProblem(_Frozen):
    """Why no event could be built. The UI turns it into a chip the user taps to fix."""

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
    status: Literal["ok", "needs_input"]
    interpretation: InterpretedDisruption | None  # None when the LLM failed
    event: DisruptionEvent | None  # set exactly when status is "ok"
    # Korean chip text filled from the event's own numbers (CLAUDE.md rule 5), e.g.
    # "14:00부터 움직일 수 있어요". Shown so the user can check what was understood.
    chips: tuple[str, ...] = ()
    problem: InterpretProblem | None = None
