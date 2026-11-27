"""Rule-based step: `EventDraft` (loose: what the user said) -> `DisruptionEvent` (engine).

Pure and deterministic: "now" is an argument and nothing here calls the LLM or a network.
All arithmetic (minutes, absolute times, "1시간 앞당겨짐" from the booked time) and all id
matching happens here, never in the LLM (invariants 4 and 5).

A gap is filled by rule only where everyday speech leaves it out on purpose, and the chip
then says what was assumed so the user can fix it (decision 2026-11-26):
- no time for rain, or for a delay -> from now ("지금(14:00)부터 비").
- "하루종일" -> from now to the end of the day.
- waiting or staying longer with no place named -> the place the user is at now.
Anything else that is missing or ambiguous becomes a question in plain Korean, never a field
name, and only that event waits for it (invariant 8): the rest are built and shown.
"""

import re
from collections.abc import Sequence

from app.schemas.disruption import EventDraft, InterpretItem, Question
from app.schemas.enums import Category
from app.schemas.events import (
    ClosureEvent,
    DelayEvent,
    DisruptionEvent,
    ExtendEvent,
    FatigueEvent,
    ReservationChangeEvent,
    WaitEvent,
    WeatherEvent,
)
from app.schemas.models import MINUTES_PER_DAY, Activity

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
DELAY_OPTIONS = (15, 30, 60, 90, 120)
EXTEND_OPTIONS = (15, 30, 45, 60)
WAIT_OPTIONS = (10, 20, 30, 40, 60)


def hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _clock(value: str | None) -> int | None:
    """ "HH:MM" -> minutes, or None when it is not a clock time."""
    if value is None:
        return None
    match = _TIME_RE.match(value.strip())
    return None if match is None else int(match.group(1)) * 60 + int(match.group(2))


def _normalize(text: str) -> str:
    return "".join(text.lower().split())


# Words that name a place by what it is rather than by its title ("점심 식당"). Matched only
# when the title itself does not match, and only when exactly one piece fits.
_MEAL_WORDS = ("식당", "레스토랑", "밥", "맛집", "restaurant")
_MEAL_TIMES = (
    ("아침", 0, 10 * 60 + 30),
    ("점심", 10 * 60 + 30, 16 * 60),
    ("저녁", 16 * 60, 24 * 60),
)
_FILLER = ("예약시간", "예약", "시간", "에서", "에", "도", "은", "는", "이", "가", "집")


def _by_kind(hint: str, activities: Sequence[Activity]) -> list[Activity]:
    words = _normalize(hint)
    meals = [a for a in activities if a.category == Category.MEAL]
    for word, start, end in _MEAL_TIMES:
        if word in words:
            return [a for a in meals if start <= a.planned_start < end]
    if any(w in words for w in _MEAL_WORDS):
        return meals
    if "카페" in words or "cafe" in words:
        return [a for a in activities if a.category == Category.CAFE]
    return []


def _strip_filler(hint: str) -> str:
    out = _normalize(hint)
    for word in _FILLER:
        if out.endswith(word) and len(out) > len(word):
            out = out[: -len(word)]
    return out


def match_activities(hint: str, activities: Sequence[Activity]) -> list[Activity]:
    """Exact title, then "one contains the other" (also without trailing particles like
    "예약"/"에서"), then a kind of place ("점심 식당" -> the lunch). Returns every fit: the
    caller uses it only when there is exactly one."""
    wanted = _normalize(hint)
    if not wanted:
        return []
    exact = [a for a in activities if _normalize(a.title) == wanted]
    if exact:
        return exact
    for w in dict.fromkeys((wanted, _strip_filler(hint))):
        found = [a for a in activities if w in _normalize(a.title) or _normalize(a.title) in w]
        if found:
            return found
    return _by_kind(hint, activities)


class _Ctx:
    def __init__(self, now: int, location_id: str, activities: Sequence[Activity]) -> None:
        self.now = now
        self.location_id = location_id
        self.activities = tuple(activities)
        self.by_id = {a.id: a for a in activities}

    @property
    def ahead(self) -> tuple[str, ...]:
        """Places still to come (not over by now), the ones worth offering as choices."""
        ids = tuple(a.id for a in self.activities if a.planned_end > self.now)
        return ids or tuple(a.id for a in self.activities)

    @property
    def here(self) -> Activity | None:
        return self.by_id.get(self.location_id)


def _ask(draft: EventDraft, question: Question) -> InterpretItem:
    return InterpretItem(draft=draft, question=question)


def _place(
    draft: EventDraft, ctx: _Ctx, text: str, *, default_here: bool = False
) -> tuple[Activity | None, bool, Question]:
    """(activity, assumed, question). `question` always comes back: it is how to pick another
    place. The activity is None when it has to be asked."""
    if draft.activity_id is not None and draft.activity_id in ctx.by_id:
        found = [ctx.by_id[draft.activity_id]]
    elif draft.activity_hint and draft.activity_hint.strip():
        found = match_activities(draft.activity_hint, ctx.activities)
    else:
        found = []
    choices = tuple(a.id for a in found) if len(found) > 1 else ctx.ahead
    question = Question(field="activity_id", kind="place", text=text, candidates=choices)
    if len(found) == 1:
        return found[0], False, question
    if not found and default_here and ctx.here is not None and not draft.activity_hint:
        return ctx.here, True, question
    return None, False, question


def _now_label(at: int, assumed: bool) -> str:
    return f"지금({hhmm(at)})" if assumed else hhmm(at)


def _delay(draft: EventDraft, ctx: _Ctx) -> InterpretItem:
    question = Question(
        field="delay_minutes", kind="minutes", text="얼마나 늦어지나요?", options=DELAY_OPTIONS
    )
    minutes = draft.delay_minutes
    if minutes is not None and minutes <= 0:
        return _ask(draft, question)
    start = ctx.now + (minutes or 0)
    if start > MINUTES_PER_DAY:
        return _ask(
            draft, question.model_copy(update={"text": "자정을 넘겨요. 얼마나 늦어지나요?"})
        )
    event = DelayEvent(occurred_at=ctx.now, location_id=ctx.location_id, start_time=start)
    assumed = minutes is None
    chip = f"{_now_label(start, assumed)}부터 움직일 수 있어요"
    return InterpretItem(draft=draft, event=event, chip=chip, assumed=assumed, question=question)


def _weather(draft: EventDraft, ctx: _Ctx) -> InterpretItem:
    question = Question(
        field="time_from", kind="time", text="비가 언제부터 오나요?", default=ctx.now
    )
    start = _clock(draft.time_from)
    if draft.time_from is not None and start is None:
        return _ask(draft, question)
    assumed = start is None
    start = ctx.now if start is None else start
    end = None if draft.whole_day else _clock(draft.time_to)
    if end is not None and end <= start:
        return _ask(
            draft,
            question.model_copy(
                update={"text": "비가 그치는 시각보다 이른 시작 시각을 알려 주세요."}
            ),
        )
    event = WeatherEvent(
        occurred_at=ctx.now, location_id=ctx.location_id, start_time=start, end_time=end
    )
    until = (
        f"{hhmm(end)}까지"
        if end is not None
        else ("하루 종일" if draft.whole_day else "끝나는 시각 미정")
    )
    chip = f"{_now_label(start, assumed)}부터 비 · {until}"
    return InterpretItem(draft=draft, event=event, chip=chip, assumed=assumed, question=question)


def _closure(draft: EventDraft, ctx: _Ctx) -> InterpretItem:
    activity, _, question = _place(draft, ctx, "어디가 문을 닫았나요?")
    if activity is None:
        return _ask(draft, question)
    event = ClosureEvent(occurred_at=ctx.now, location_id=ctx.location_id, activity_id=activity.id)
    return InterpretItem(
        draft=draft, event=event, chip=f"{activity.title} 이용 불가", question=question
    )


def _fatigue(draft: EventDraft, ctx: _Ctx) -> InterpretItem:
    event = FatigueEvent(occurred_at=ctx.now, location_id=ctx.location_id)
    chip = f"걷는 일정은 원래 길이의 {event.walking_ratio:.0%} 이하로 줄여요"
    return InterpretItem(draft=draft, event=event, chip=chip)


def _positive(value: int | None) -> int | None:
    return value if value is not None and value > 0 else None


def _extend(draft: EventDraft, ctx: _Ctx) -> InterpretItem:
    activity, assumed, place_q = _place(draft, ctx, "어디에서 더 머물까요?", default_here=True)
    if activity is None:
        return _ask(draft, place_q)
    minutes_q = Question(
        field="extra_minutes",
        kind="minutes",
        text=f"{activity.title}에서 얼마나 더 머물까요?",
        options=EXTEND_OPTIONS,
    )
    extra = _positive(draft.extra_minutes)
    if extra is None:
        return _ask(draft, minutes_q)
    event = ExtendEvent(
        occurred_at=ctx.now,
        location_id=ctx.location_id,
        activity_id=activity.id,
        extra_minutes=extra,
    )
    chip = f"{activity.title} {extra}분 더 머물기"
    return InterpretItem(draft=draft, event=event, chip=chip, assumed=assumed, question=minutes_q)


def _wait(draft: EventDraft, ctx: _Ctx) -> InterpretItem:
    activity, assumed, place_q = _place(draft, ctx, "어디에서 기다리나요?", default_here=True)
    if activity is None:
        return _ask(draft, place_q)
    minutes_q = Question(
        field="wait_minutes",
        kind="minutes",
        text=f"{activity.title}에서 얼마나 기다려야 하나요?",
        options=WAIT_OPTIONS,
    )
    minutes = _positive(draft.wait_minutes)
    if minutes is None:
        return _ask(draft, minutes_q)
    event = WaitEvent(
        occurred_at=ctx.now, location_id=ctx.location_id, activity_id=activity.id, minutes=minutes
    )
    chip = f"{activity.title} 대기 {minutes}분"
    return InterpretItem(draft=draft, event=event, chip=chip, assumed=assumed, question=minutes_q)


def _reservation(draft: EventDraft, ctx: _Ctx) -> InterpretItem:
    activity, _, place_q = _place(draft, ctx, "어떤 예약이 바뀌었나요?")
    if activity is None:
        booked = tuple(a.id for a in ctx.activities if a.reservation_time is not None)
        if booked and not draft.activity_hint:
            place_q = place_q.model_copy(update={"candidates": booked})
        return _ask(draft, place_q)
    booked_at = activity.reservation_time
    before = booked_at if booked_at is not None else activity.planned_start
    time_q = Question(
        field="new_time",
        kind="time",
        text=f"{activity.title} 예약이 몇 시로 바뀌었나요?",
        default=before,
    )
    new_time = _clock(draft.new_time)
    if new_time is None and draft.new_time is None and draft.shift_minutes:
        new_time = before + draft.shift_minutes  # "1시간 앞당겨짐": from the booked time, by rule
    if new_time is None or not 0 <= new_time <= MINUTES_PER_DAY:
        return _ask(draft, time_q)
    event = ReservationChangeEvent(
        occurred_at=ctx.now,
        location_id=ctx.location_id,
        activity_id=activity.id,
        new_time=new_time,
    )
    # A title that already says "예약" ("에펠탑 예약") does not get it twice.
    booking = (
        activity.title if activity.title.rstrip().endswith("예약") else f"{activity.title} 예약"
    )
    chip = f"{booking} {hhmm(before)} → {hhmm(new_time)}"
    return InterpretItem(draft=draft, event=event, chip=chip, question=time_q)


_TYPE_QUESTION = Question(field="type", kind="type", text="어떤 일이 있었나요?")
_RULES = {
    "DELAY": _delay,
    "WEATHER": _weather,
    "CLOSURE": _closure,
    "FATIGUE": _fatigue,
    "EXTEND": _extend,
    "WAIT": _wait,
    "RESERVATION_CHANGE": _reservation,
}


def build_item(
    draft: EventDraft, *, now: int, location_id: str, activities: Sequence[Activity]
) -> InterpretItem:
    """One draft -> its event and chip, or the question that stands in the way."""
    ctx = _Ctx(now, location_id, activities)
    if draft.type == "MUST_VISIT":
        # Needs the place found on the map first, not just words.
        return _ask(
            draft,
            Question(
                field="type",
                kind="add_place",
                text="새로 넣을 곳은 '꼭 가고 싶은 곳 추가'에서 지도로 골라 주세요.",
            ),
        )
    rule = _RULES.get(draft.type)
    return _ask(draft, _TYPE_QUESTION) if rule is None else rule(draft, ctx)


def built_events(items: Sequence[InterpretItem]) -> tuple[DisruptionEvent, ...]:
    """The events ready for the engine, in order, keeping only the first per (type, place):
    the engine takes one booking time or one queue per piece."""
    seen: set[tuple[str, str | None]] = set()
    out: list[DisruptionEvent] = []
    for item in items:
        ev = item.event
        if ev is None:
            continue
        key = (ev.type, getattr(ev, "activity_id", None))
        # Delays and rain stack (the engine takes the latest start / every window).
        if key in seen and ev.type not in ("DELAY", "WEATHER"):
            continue
        seen.add(key)
        out.append(ev)
    return tuple(out)
