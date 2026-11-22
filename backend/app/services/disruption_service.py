"""Step ④–⑤ as one call: text -> (LLM) loose interpretation -> (rules) engine event + chips.

I/O (the LLM call) happens here, never in the engine (invariant 1). Every failure on the way
becomes a `needs_input` answer instead of an error or a guess (invariants 4 and 8).
"""

from app.llm.disruption_interpreter import InterpretedDisruption, interpret
from app.llm.provider import LLMOutputError, LLMProvider
from app.schemas.disruption import InterpretProblem, InterpretRequest, InterpretResponse
from app.schemas.events import (
    ClosureEvent,
    DelayEvent,
    DisruptionEvent,
    ExtendEvent,
    FatigueEvent,
    ReservationChangeEvent,
    WeatherEvent,
)
from app.schemas.models import Activity
from app.services.event_builder import EventBuildError, build_event


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def event_chips(event: DisruptionEvent, activities: tuple[Activity, ...]) -> tuple[str, ...]:
    """What the engine will be told, in words. Every number comes from the event itself."""
    title = {a.id: a.title for a in activities}
    match event:
        case DelayEvent():
            return (f"{_hhmm(event.start_time)}부터 움직일 수 있어요",)
        case WeatherEvent():
            end = (
                f"{_hhmm(event.end_time)}까지" if event.end_time is not None else "끝나는 시각 미정"
            )
            return (f"{_hhmm(event.start_time)}부터 비 · {end}",)
        case ClosureEvent():
            return (f"{title[event.activity_id]} 이용 불가",)
        case FatigueEvent():
            return (f"걷는 일정은 원래 길이의 {event.walking_ratio:.0%} 이하로 줄여요",)
        case ExtendEvent():
            return (f"{title[event.activity_id]} {event.extra_minutes}분 더 머물기",)
        case ReservationChangeEvent():
            return (f"{title[event.activity_id]} 예약 {_hhmm(event.new_time)}로 변경",)
        case _:  # MUST_VISIT never reaches here: build_event refuses it
            return ()


def interpret_disruption(req: InterpretRequest, provider: LLMProvider) -> InterpretResponse:
    try:
        interpretation: InterpretedDisruption | None = interpret(provider, req.text)
    except LLMOutputError as exc:
        problem = InterpretProblem(code="LLM_FAILED", detail=str(exc))
        return InterpretResponse(
            status="needs_input", interpretation=None, event=None, problem=problem
        )

    try:
        event = build_event(
            interpretation,
            now=req.now,
            location_id=req.location_id,
            activities=req.activities,
        )
    except EventBuildError as exc:
        problem = InterpretProblem(code=exc.code, detail=exc.detail, candidates=exc.candidates)
        return InterpretResponse(
            status="needs_input", interpretation=interpretation, event=None, problem=problem
        )
    return InterpretResponse(
        status="ok",
        interpretation=interpretation,
        event=event,
        chips=event_chips(event, req.activities),
    )
