"""Rule-based step: `InterpretedDisruption` (loose, from the LLM) -> `DisruptionEvent` (engine).

Pure and deterministic: "now" is an argument and nothing here calls the LLM or a network.
All arithmetic (minutes, absolute times) and all id matching happens here, never in the LLM
(invariants 4 and 5). Whenever the text is missing something or is ambiguous, it raises
`EventBuildError` instead of guessing (invariant 8); the UI turns that into a chip the user fixes.
"""

import re
from collections.abc import Sequence
from typing import Literal

from app.llm.disruption_interpreter import InterpretedDisruption
from app.schemas.events import (
    ClosureEvent,
    DelayEvent,
    DisruptionEvent,
    ExtendEvent,
    FatigueEvent,
    ReservationChangeEvent,
    WeatherEvent,
)
from app.schemas.models import MINUTES_PER_DAY, Activity

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")

ErrorCode = Literal[
    "UNKNOWN_TYPE",  # LLM could not tell what happened
    "UNSUPPORTED",  # MUST_VISIT: needs place data, not just words
    "MISSING_FIELD",  # the text did not say something the event needs
    "BAD_TIME",  # not "HH:MM", or the times do not make sense
    "NO_MATCH",  # no activity title matches the hint
    "AMBIGUOUS",  # several activity titles match the hint
]


class EventBuildError(Exception):
    """Ask the user. `candidates` are activity ids the UI can offer as chips."""

    def __init__(self, code: ErrorCode, detail: str, candidates: tuple[str, ...] = ()) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.candidates = candidates


def _minutes(value: str | None, field: str) -> int:
    if value is None:
        raise EventBuildError("MISSING_FIELD", field)
    match = _TIME_RE.match(value.strip())
    if match is None:
        raise EventBuildError("BAD_TIME", f"{field}={value!r}")
    return int(match.group(1)) * 60 + int(match.group(2))


def _positive(value: int | None, field: str) -> int:
    if value is None:
        raise EventBuildError("MISSING_FIELD", field)
    if value <= 0:
        raise EventBuildError("BAD_TIME", f"{field}={value}")
    return value


def _normalize(text: str) -> str:
    return "".join(text.lower().split())


def match_activity(hint: str | None, activities: Sequence[Activity]) -> Activity:
    """Exact title first, then "one contains the other". Never picks when it is not unique."""
    if hint is None or not _normalize(hint):
        raise EventBuildError("MISSING_FIELD", "activity_hint", tuple(a.id for a in activities))
    wanted = _normalize(hint)
    exact = [a for a in activities if _normalize(a.title) == wanted]
    found = exact or [
        a for a in activities if wanted in _normalize(a.title) or _normalize(a.title) in wanted
    ]
    if len(found) == 1:
        return found[0]
    if not found:
        raise EventBuildError("NO_MATCH", hint, tuple(a.id for a in activities))
    raise EventBuildError("AMBIGUOUS", hint, tuple(a.id for a in found))


def build_event(
    interp: InterpretedDisruption,
    *,
    now: int,
    location_id: str,
    activities: Sequence[Activity],
) -> DisruptionEvent:
    base = {"occurred_at": now, "location_id": location_id}
    match interp.type:
        case "DELAY":
            start = now + _positive(interp.delay_minutes, "delay_minutes")
            if start > MINUTES_PER_DAY:
                raise EventBuildError("BAD_TIME", f"delay ends after midnight ({start} min)")
            return DelayEvent(**base, start_time=start)
        case "WEATHER":
            start = _minutes(interp.time_from, "time_from")
            end = _minutes(interp.time_to, "time_to") if interp.time_to is not None else None
            if end is not None and end <= start:
                raise EventBuildError("BAD_TIME", "time_to must be after time_from")
            return WeatherEvent(**base, start_time=start, end_time=end)
        case "CLOSURE":
            activity = match_activity(interp.activity_hint, activities)
            return ClosureEvent(**base, activity_id=activity.id)
        case "FATIGUE":
            return FatigueEvent(**base)
        case "EXTEND":
            activity = match_activity(interp.activity_hint, activities)
            extra = _positive(interp.extra_minutes, "extra_minutes")
            return ExtendEvent(**base, activity_id=activity.id, extra_minutes=extra)
        case "RESERVATION_CHANGE":
            activity = match_activity(interp.activity_hint, activities)
            new_time = _minutes(interp.new_time, "new_time")
            return ReservationChangeEvent(**base, activity_id=activity.id, new_time=new_time)
        case "MUST_VISIT":
            raise EventBuildError("UNSUPPORTED", "MUST_VISIT needs a place lookup, not text alone")
        case _:
            raise EventBuildError("UNKNOWN_TYPE", interp.type)
