"""Step ④–⑤: text -> (LLM) events + wishes as heard -> (rules) engine events, chips, questions.

I/O (the LLM call) happens here, never in the engine (invariant 1). Nothing on the way fails the
whole answer: what was understood comes back as chips, and only what is missing is asked
(decision 2026-11-26). Editing a chip or answering a question runs the rules again on the
edited drafts (`build_disruption`), without the LLM.
"""

from collections.abc import Sequence

from app.llm.disruption_interpreter import InterpretedMessage, interpret, said
from app.llm.provider import LLMOutputError, LLMProvider
from app.schemas.disruption import (
    MAX_ITEMS,
    BuildRequest,
    EventDraft,
    InterpretItem,
    InterpretProblem,
    InterpretRequest,
    InterpretResponse,
    Question,
    WishChip,
)
from app.schemas.enums import Wish
from app.schemas.events import DelayEvent
from app.schemas.models import Activity
from app.services.event_builder import build_item, built_events

WISH_CHIPS: dict[Wish, str] = {
    Wish.INDOOR: "실내 위주로 · 야외 조각은 실내 장소를 먼저 찾아요",
    Wish.REST: "여유 있게 · 조각 사이를 넉넉히 비워요",
}
# Wishes that are a FATIGUE event for the engine (less walking): added once, as a draft, so the
# user sees it as a chip and can remove it like any other.
_FATIGUE_WISHES = (Wish.LESS_WALKING, Wish.REST)

_PROBLEM_CODE = {
    "type": "UNKNOWN_TYPE",
    "activity_id": "NO_MATCH",
}


def _rain_said_when(e) -> bool:
    return bool(e.time_from or e.time_to or e.whole_day)


def drafts_from(
    message: InterpretedMessage, text: str
) -> tuple[tuple[EventDraft, ...], tuple[Wish, ...]]:
    """The LLM's reading as editable drafts. A wish counts only when its evidence is in `text`
    (the traveler said it). The same event heard twice is one ("비 와서" -> WEATHER twice, live
    test 2026-11-27). UNKNOWN items are kept only when nothing else was understood (then the user
    is asked what happened); a less-walking or rest wish adds one FATIGUE draft when the message
    had none."""
    wishes = tuple(dict.fromkeys(Wish(w.wish) for w in message.wishes if said(w.evidence, text)))
    unique = list({e.model_dump_json(): e for e in message.events}.values())
    # "15시까지 비" also heard as a bare "비": the bare one says nothing more (live test).
    timed = any(e.type == "WEATHER" and _rain_said_when(e) for e in unique)
    unique = [e for e in unique if not (timed and e.type == "WEATHER" and not _rain_said_when(e))]
    drafts = [EventDraft(**e.model_dump()) for e in unique]
    known = [d for d in drafts if d.type != "UNKNOWN"]
    if any(w in wishes for w in _FATIGUE_WISHES) and not any(d.type == "FATIGUE" for d in known):
        known.append(EventDraft(type="FATIGUE"))
    if known:
        drafts = known
    elif wishes:
        drafts = []  # a wish alone is a complete answer ("실내에 있고 싶어요")
    else:
        drafts = drafts[:1] or [EventDraft(type="UNKNOWN")]
    return tuple(drafts[:MAX_ITEMS]), wishes


def respond(
    drafts: Sequence[EventDraft],
    wishes: Sequence[Wish],
    *,
    now: int,
    location_id: str,
    activities: Sequence[Activity],
) -> InterpretResponse:
    items = tuple(
        build_item(d, now=now, location_id=location_id, activities=activities) for d in drafts
    )
    events = built_events(items)
    wishes = tuple(dict.fromkeys(wishes))
    open_items = [i for i in items if i.event is None]
    wish_chips = tuple(WishChip(wish=w, text=WISH_CHIPS[w]) for w in wishes if w in WISH_CHIPS)
    chips = (
        *(i.chip for i in items if i.event is not None and i.chip),
        *(c.text for c in wish_chips),
    )
    # Ready when every event is built and there is something to act on. A wish alone ("실내에
    # 있고 싶어요") still needs an event for the engine: "from now", nothing else happened.
    if not open_items and not events and wishes:
        return _wish_only(wishes, now, location_id, chips, wish_chips)
    ok = not open_items and bool(events)
    return InterpretResponse(
        status="ok" if ok else "needs_input",
        event=events[0] if events and ok else None,
        events=events,
        items=items,
        wishes=wishes,
        chips=chips,
        wish_chips=wish_chips,
        problem=None if ok else _problem(open_items[0] if open_items else None),
    )


def _wish_only(
    wishes: tuple[Wish, ...],
    now: int,
    location_id: str,
    chips: tuple[str, ...],
    wish_chips: tuple[WishChip, ...],
) -> InterpretResponse:
    # No event was said: the day goes on from now (a delay of zero), shaped by the wishes.
    event = DelayEvent(occurred_at=now, location_id=location_id, start_time=now)
    return InterpretResponse(
        status="ok",
        event=event,
        events=(event,),
        items=(),
        wishes=wishes,
        chips=chips,
        wish_chips=wish_chips,
    )


def _problem(item: InterpretItem | None) -> InterpretProblem:
    question = item.question if item is not None else None
    if question is None:
        return InterpretProblem(code="UNKNOWN_TYPE", detail="어떤 일이 있었나요?")
    if question.kind == "add_place":
        code = "UNSUPPORTED"
    else:
        code = _PROBLEM_CODE.get(question.field, "MISSING_FIELD")
    return InterpretProblem(code=code, detail=question.text, candidates=question.candidates)


_TYPE_QUESTION = Question(
    field="type", kind="type", text="어떤 일이 있었나요? 아래에서 골라 주세요."
)


def interpret_disruption(req: InterpretRequest, provider: LLMProvider) -> InterpretResponse:
    try:
        message = interpret(provider, req.text)
    except LLMOutputError:
        item = InterpretItem(draft=EventDraft(type="UNKNOWN"), question=_TYPE_QUESTION)
        problem = InterpretProblem(code="LLM_FAILED", detail=_TYPE_QUESTION.text)
        return InterpretResponse(status="needs_input", event=None, items=(item,), problem=problem)
    drafts, wishes = drafts_from(message, req.text)
    return respond(
        drafts, wishes, now=req.now, location_id=req.location_id, activities=req.activities
    )


def build_disruption(req: BuildRequest) -> InterpretResponse:
    return respond(
        req.drafts,
        req.wishes,
        now=req.now,
        location_id=req.location_id,
        activities=req.activities,
    )
