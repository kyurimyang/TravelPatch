"""Shared by the fixed-reading and the live multi-event tests: solve what was understood, then
check that every candidate answers EVERY event the way a traveller would expect.

The validator already proves no hard rule is broken; these checks ask a different question:
does the plan do what the person asked for? (the booking is at its new time, the queue is in the
lunch, the closed place is not visited, nothing outdoors in the rain, walking pieces are shorter,
the extension is there), plus what the case expects of the set of candidates.
"""

from math import ceil

from app.schemas.disruption import InterpretResponse
from app.schemas.events import (
    ClosureEvent,
    ExtendEvent,
    FatigueEvent,
    ReservationChangeEvent,
    WaitEvent,
    WeatherEvent,
)
from app.schemas.models import MINUTES_PER_DAY
from app.schemas.recovery import RecoveryInput, RecoveryResponse, RecoveryResult
from app.services.recovery_service import run_recovery
from app.services.visited import apply_visited


def solve(
    day: RecoveryInput, now: int, res: InterpretResponse
) -> tuple[RecoveryInput, RecoveryResponse]:
    data = day.model_dump()
    data |= {
        "event": res.events[0].model_dump(),
        "more_events": [e.model_dump() for e in res.events[1:]],
        "wishes": [w.value for w in res.wishes],
    }
    inp = RecoveryInput.model_validate(data)
    targets = {getattr(e, "activity_id", None) for e in res.events}
    visited = [a.id for a in inp.activities if a.planned_end <= now and a.id not in targets]
    inp = apply_visited(inp, visited)
    return inp, run_recovery(inp)


def _outdoors(inp: RecoveryInput, activity_id: str, substitute_id: str | None) -> bool:
    own = next(a.outdoor for a in inp.activities if a.id == activity_id)
    if substitute_id:
        sub = next(s for s in inp.substitutes if s.id == substitute_id)
        return (own if sub.outdoor is None else sub.outdoor) is True
    return own is True


def problems(inp: RecoveryInput, result: RecoveryResult) -> list[str]:
    """What this candidate fails to do for the events, in words. Empty = it answers them all."""
    acts = {a.id: a for a in inp.activities}
    by_id = {c.activity_id: c for c in result.changes}
    out: list[str] = []
    for ev in inp.events:
        if isinstance(ev, ReservationChangeEvent):
            c = by_id[ev.activity_id]
            if c.after is not None and c.substitute_id is None and c.after.start != ev.new_time:
                out.append(f"{ev.activity_id}: not at its new booking time")
        elif isinstance(ev, WaitEvent):
            c = by_id[ev.activity_id]
            if c.after is not None and c.substitute_id is None:
                if c.after.end - c.after.start < acts[ev.activity_id].min_duration + ev.minutes:
                    out.append(f"{ev.activity_id}: the queue is not in its time")
        elif isinstance(ev, ClosureEvent):
            c = by_id[ev.activity_id]
            if c.after is not None and c.substitute_id is None:
                out.append(f"{ev.activity_id}: still visited though closed")
        elif isinstance(ev, WeatherEvent):
            end = ev.end_time if ev.end_time is not None else MINUTES_PER_DAY
            for c in result.changes:
                if c.after is None or c.activity_id not in acts:
                    continue
                wet = c.after.start < end and c.after.end > ev.start_time
                if wet and _outdoors(inp, c.activity_id, c.substitute_id):
                    out.append(f"{c.activity_id}: outdoors in the rain")
        elif isinstance(ev, FatigueEvent):
            for a in inp.activities:
                c = by_id[a.id]
                if not a.walking or a.reservation_time is not None or a.id == ev.location_id:
                    continue
                if c.after is None or c.substitute_id is not None:
                    continue
                planned = a.planned_end - a.planned_start
                cap = max(a.min_duration, ceil(planned * ev.walking_ratio / 5) * 5)
                if c.after.end - c.after.start > cap:
                    out.append(f"{a.id}: a walking piece is not shorter")
        elif isinstance(ev, ExtendEvent):
            c = by_id[ev.activity_id]
            a = acts[ev.activity_id]
            if (
                c.after is None
                or c.after.end - c.after.start < a.planned_end - a.planned_start + ev.extra_minutes
            ):
                out.append(f"{ev.activity_id}: not extended as asked")
    return out


def in_words(inp: RecoveryInput, result: RecoveryResult) -> list[str]:
    """The candidate as a person would read it: every piece that changes, with its new time."""
    titles = {a.id: a.title for a in inp.activities} | {s.id: s.title for s in inp.substitutes}

    def hhmm(m: int) -> str:
        return f"{m // 60:02d}:{m % 60:02d}"

    out = []
    for c in result.changes:
        if c.op == "keep":
            continue
        where = f" → {titles[c.substitute_id]}" if c.substitute_id else ""
        when = f" {hhmm(c.after.start)}–{hhmm(c.after.end)}" if c.after else ""
        out.append(f"{titles.get(c.activity_id, c.activity_id)}: {c.op}{where}{when}")
    return out


def case_problems(case: dict, inp: RecoveryInput, out: RecoveryResponse) -> list[str]:
    """Every candidate checked, plus what the case expects of the set of them."""
    want = case["expect"]
    found: list[str] = []
    if not out.candidates:
        return ["no patch at all"]
    for r in out.candidates:
        found += [f"[{r.strategy}] {p}" for p in problems(inp, r)]
    if "first_strategy" in want and out.candidates[0].strategy != want["first_strategy"]:
        found.append(
            f"first candidate is {out.candidates[0].strategy}, not {want['first_strategy']}"
        )
    if want.get("distinct") and len({r.changes for r in out.candidates}) < 2:
        found.append("the candidates do not offer different choices")
    return found
