"""Independent hard-constraint checker.

Must not import the solver (optimizer_dp, local_search): it re-simulates a candidate from
the raw input so a solver bug cannot hide itself.
"""

from itertools import pairwise
from math import ceil
from typing import NamedTuple

from pydantic import BaseModel

from app.schemas.enums import Op, Tier
from app.schemas.events import (
    DelayEvent,
    ExtendEvent,
    FatigueEvent,
    MustVisitEvent,
    WeatherEvent,
)
from app.schemas.models import HOTEL_ID, MINUTES_PER_DAY
from app.schemas.recovery import RecoveryChange, RecoveryInput


class Violation(BaseModel):
    kind: str
    activity_id: str
    detail: str


class _Info(NamedTuple):
    open_at: int | None
    close_at: int | None
    min_duration: int
    reservation_time: int | None
    is_must: bool


def _info(inp: RecoveryInput) -> dict[str, _Info]:
    tiers = {p.activity_id: p.tier for p in inp.preferences}
    info = {
        a.id: _Info(
            a.open_at, a.close_at, a.min_duration, a.reservation_time, tiers[a.id] == Tier.MUST
        )
        for a in inp.activities
    }
    ev = inp.event
    if isinstance(ev, MustVisitEvent):
        info[ev.activity_id] = _Info(ev.open_at, ev.close_at, ev.min_duration, None, True)
    return info


def _travel_table(inp: RecoveryInput) -> dict[frozenset[str], int]:
    # Travel pairs are undirected, so a frozenset key finds A-B and B-A alike.
    return {frozenset((t.a, t.b)): t.minutes for t in inp.travel}


def _placed(changes: tuple[RecoveryChange, ...]) -> list[RecoveryChange]:
    # Dropped activities have no "after". Sort by start, then id, so results are deterministic.
    return sorted(
        (c for c in changes if c.after is not None),
        key=lambda c: (c.after.start, c.activity_id),
    )


def _check_coverage(info: dict[str, _Info], changes: tuple[RecoveryChange, ...]) -> list[Violation]:
    ids = [c.activity_id for c in changes]
    out: list[Violation] = []
    for i in sorted(set(info) - set(ids)):
        out.append(Violation(kind="coverage", activity_id=i, detail=f"{i} has no change entry"))
    for i in sorted(set(ids) - set(info)):
        out.append(Violation(kind="coverage", activity_id=i, detail=f"{i} is not in the input"))
    for i in sorted({i for i in ids if ids.count(i) > 1}):
        out.append(Violation(kind="coverage", activity_id=i, detail=f"{i} appears more than once"))
    return out


def _now(inp: RecoveryInput) -> int:
    # A delayed user can move again only at start_time; otherwise "now" is occurred_at.
    ev = inp.event
    return ev.start_time if isinstance(ev, DelayEvent) else ev.occurred_at


def _check_past(inp: RecoveryInput, changes: tuple[RecoveryChange, ...]) -> list[Violation]:
    now = _now(inp)
    out: list[Violation] = []
    for c in sorted(changes, key=lambda c: c.activity_id):
        if c.after is None:
            continue
        start_changed = c.before is None or c.after.start != c.before.start
        if start_changed and c.after.start < now:
            out.append(
                Violation(
                    kind="past",
                    activity_id=c.activity_id,
                    detail=f"{c.activity_id} starts at {c.after.start}, before now ({now})",
                )
            )
    return out


def _check_must_kept(info: dict[str, _Info], changes: tuple[RecoveryChange, ...]) -> list[Violation]:
    return [
        Violation(kind="must_drop", activity_id=c.activity_id, detail=f"{c.activity_id} is must")
        for c in sorted(changes, key=lambda c: c.activity_id)
        if c.op == Op.DROP and info[c.activity_id].is_must
    ]


def _check_each_activity(info: dict[str, _Info], placed: list[RecoveryChange]) -> list[Violation]:
    out: list[Violation] = []
    for c in placed:
        i = info[c.activity_id]
        start, end = c.after.start, c.after.end
        if i.reservation_time is not None and start != i.reservation_time:
            out.append(
                Violation(
                    kind="reservation",
                    activity_id=c.activity_id,
                    detail=f"starts at {start}, reserved for {i.reservation_time}",
                )
            )
        if i.open_at is not None and start < i.open_at:
            out.append(
                Violation(
                    kind="hours",
                    activity_id=c.activity_id,
                    detail=f"starts at {start}, opens at {i.open_at}",
                )
            )
        if i.close_at is not None and end > i.close_at:
            out.append(
                Violation(
                    kind="hours",
                    activity_id=c.activity_id,
                    detail=f"ends at {end}, closes at {i.close_at}",
                )
            )
        if end - start < i.min_duration:
            out.append(
                Violation(
                    kind="duration",
                    activity_id=c.activity_id,
                    detail=f"lasts {end - start} min, minimum is {i.min_duration}",
                )
            )
    return out


def _check_travel(
    inp: RecoveryInput, placed: list[RecoveryChange], min_buffer: int
) -> list[Violation]:
    travel = _travel_table(inp)
    out: list[Violation] = []
    for prev, nxt in pairwise(placed):
        need = travel[frozenset((prev.activity_id, nxt.activity_id))] + min_buffer
        earliest = prev.after.end + need
        if nxt.after.start < earliest:
            out.append(
                Violation(
                    kind="travel",
                    activity_id=nxt.activity_id,
                    detail=(
                        f"{nxt.activity_id} starts at {nxt.after.start} but "
                        f"{prev.activity_id} ends at {prev.after.end} + {need} min travel/buffer"
                    ),
                )
            )
    return out


def _check_origin(inp: RecoveryInput, placed: list[RecoveryChange]) -> list[Violation]:
    # The first activity still ahead must be reachable from where the user is now.
    now = _now(inp)
    ahead = [c for c in placed if c.after.start >= now]
    if not ahead:
        return []
    first = ahead[0]
    here = inp.event.location_id
    need = 0 if here == first.activity_id else _travel_table(inp)[frozenset((here, first.activity_id))]
    if first.after.start >= now + need:
        return []
    return [
        Violation(
            kind="origin",
            activity_id=first.activity_id,
            detail=f"starts at {first.after.start}; from {here} the earliest is {now + need}",
        )
    ]


def _check_weather(inp: RecoveryInput, placed: list[RecoveryChange]) -> list[Violation]:
    ev = inp.event
    if not isinstance(ev, WeatherEvent):
        return []
    rain_end = ev.end_time if ev.end_time is not None else MINUTES_PER_DAY
    outdoor = {a.id for a in inp.activities if a.outdoor}  # unknown (None) is not blocked
    return [
        Violation(
            kind="weather",
            activity_id=c.activity_id,
            detail=f"outdoor activity overlaps the rain ({ev.start_time}-{rain_end})",
        )
        for c in placed
        if c.activity_id in outdoor and c.after.start < rain_end and c.after.end > ev.start_time
    ]


def _check_fatigue(inp: RecoveryInput, placed: list[RecoveryChange]) -> list[Violation]:
    ev = inp.event
    if not isinstance(ev, FatigueEvent):
        return []
    acts = {a.id: a for a in inp.activities}
    out: list[Violation] = []
    for c in placed:
        a = acts.get(c.activity_id)
        if a is None or not a.walking or a.reservation_time is not None:
            continue
        if a.id == ev.location_id:
            continue
        planned = a.planned_end - a.planned_start
        cap = max(a.min_duration, ceil(planned * ev.walking_ratio / 5) * 5)
        if c.after.end - c.after.start > cap:
            out.append(
                Violation(
                    kind="fatigue",
                    activity_id=c.activity_id,
                    detail=f"walking activity lasts {c.after.end - c.after.start} min, max {cap}",
                )
            )
    return out


def _check_event(inp: RecoveryInput, changes: tuple[RecoveryChange, ...]) -> list[Violation]:
    # Constraints that come straight from the user's event.
    ev = inp.event
    if not isinstance(ev, ExtendEvent):
        return []
    target = next(a for a in inp.activities if a.id == ev.activity_id)
    change = next(c for c in changes if c.activity_id == ev.activity_id)
    wanted = (target.planned_end - target.planned_start) + ev.extra_minutes
    if change.after is None or change.after.end - change.after.start < wanted:
        return [
            Violation(
                kind="event",
                activity_id=ev.activity_id,
                detail=f"must be extended to {wanted} min as requested",
            )
        ]
    return []


def _check_in_progress(inp: RecoveryInput, changes: tuple[RecoveryChange, ...]) -> list[Violation]:
    # An activity the user is in right now has already started and cannot end in the past.
    change = next((c for c in changes if c.activity_id == inp.event.location_id), None)
    if change is None or change.after is None or change.before is None:
        return []
    out: list[Violation] = []
    if change.after.start != change.before.start:
        out.append(
            Violation(
                kind="in_progress",
                activity_id=change.activity_id,
                detail="already started, its start cannot move",
            )
        )
    if change.after.end < _now(inp):
        out.append(
            Violation(
                kind="in_progress",
                activity_id=change.activity_id,
                detail="cannot end before now",
            )
        )
    return out


def _check_deadline(inp: RecoveryInput, placed: list[RecoveryChange]) -> list[Violation]:
    if not placed:
        return []
    last = max(placed, key=lambda c: (c.after.end, c.activity_id))
    back = _travel_table(inp)[frozenset((last.activity_id, HOTEL_ID))]
    arrival = last.after.end + back
    if arrival <= inp.day.end_deadline:
        return []
    return [
        Violation(
            kind="deadline",
            activity_id=last.activity_id,
            detail=f"back at hotel at {arrival}, deadline is {inp.day.end_deadline}",
        )
    ]


def validate(
    inp: RecoveryInput, changes: tuple[RecoveryChange, ...], min_buffer: int = 0
) -> list[Violation]:
    info = _info(inp)
    coverage = _check_coverage(info, changes)
    if coverage:
        # Without a complete change list the other checks cannot be trusted.
        return coverage
    placed = _placed(changes)
    return [
        *_check_past(inp, changes),
        *_check_must_kept(info, changes),
        *_check_each_activity(info, placed),
        *_check_event(inp, changes),
        *_check_weather(inp, placed),
        *_check_fatigue(inp, placed),
        *_check_in_progress(inp, changes),
        *_check_origin(inp, placed),
        *_check_travel(inp, placed, min_buffer),
        *_check_deadline(inp, placed),
    ]
