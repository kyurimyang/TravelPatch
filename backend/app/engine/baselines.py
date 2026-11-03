"""Naive baselines for the comparison experiment (CLAUDE.md section 10, (a) and (b)).

Both keep the original order, never shrink, never substitute and only understand time:
they push activities later when "now" or an extension requires it. They are blind to
weather and tiredness on purpose (that is what a simple method would do); the independent
validator counts what they break. When the day overflows (deadline, closing time, a
reserved slot missed) they drop an activity and place again. They differ only in WHO goes:

- right_shift: the latest droppable activity at or before the one that failed (position).
- greedy: the lowest-value droppable one at or before it (value; ties -> later, then id).

"must", an asked-for extension and the activity the user is in right now are never dropped.
Pure functions: no clock, no I/O.
"""

from collections.abc import Callable

from app.engine.constraint_builder import build_constraints
from app.engine.cost import compute_cost
from app.engine.presets import DEFAULT_WEIGHTS
from app.engine.validator import validate
from app.schemas.enums import Op, Tier
from app.schemas.models import HOTEL_ID, MINUTES_PER_DAY, Activity
from app.schemas.recovery import RecoveryChange, RecoveryInput, RecoveryResult, Slot

# (positions of the remaining order that may be dropped, value per id) -> index to drop
_Victim = Callable[[list[int], tuple[str, ...], dict[str, int]], int]


def _place(
    inp: RecoveryInput, order: tuple[str, ...], acts: dict[str, Activity], extend: dict[str, int]
) -> list[tuple[int, int]]:
    table = {frozenset((t.a, t.b)): t.minutes for t in inp.travel}

    def travel(a: str, b: str) -> int:
        return 0 if a == b else table[frozenset((a, b))]

    slots: list[tuple[int, int]] = []
    t, prev = inp.now, inp.event.location_id
    for act_id in order:
        a = acts[act_id]
        earliest = t + travel(prev, act_id)
        if a.open_at is not None:
            earliest = max(earliest, a.open_at)
        base = a.reservation_time if a.reservation_time is not None else a.planned_start
        start = a.planned_start if inp.event.location_id == act_id else max(base, earliest)
        end = start + (a.planned_end - a.planned_start) + extend.get(act_id, 0)
        slots.append((start, end))
        t, prev = end, act_id
    return slots


def _first_failure(
    inp: RecoveryInput, order: tuple[str, ...], acts: dict[str, Activity], slots: list[tuple[int, int]]
) -> int | None:
    table = {frozenset((t.a, t.b)): t.minutes for t in inp.travel}
    deadline = inp.day.end_deadline
    for i, (act_id, (start, end)) in enumerate(zip(order, slots, strict=True)):
        a = acts[act_id]
        late_for_reservation = a.reservation_time is not None and start > a.reservation_time
        if late_for_reservation or end > deadline or (a.close_at is not None and end > a.close_at):
            return i
    if order:
        last = order[-1]
        if slots[-1][1] + table[frozenset((last, HOTEL_ID))] > deadline:
            return len(order) - 1
    return None


def _run(inp: RecoveryInput, name: str, pick: _Victim) -> RecoveryResult:
    acts = {a.id: a for a in inp.activities}
    values = {p.activity_id: p.tier.weight for p in inp.preferences}
    musts = {p.activity_id for p in inp.preferences if p.tier == Tier.MUST}
    extend = dict(build_constraints(inp).extensions)
    protected = musts | set(extend) | {inp.event.location_id}
    full = tuple(a.id for a in sorted(inp.activities, key=lambda a: (a.planned_start, a.id)))

    order = full
    while True:
        slots = _place(inp, order, acts, extend)
        failed = _first_failure(inp, order, acts, slots)
        if failed is None:
            break
        candidates = [i for i in range(failed + 1) if order[i] not in protected]
        if not candidates:
            break  # nothing left to give up: the validator will report the violation
        drop = pick(candidates, order, values)
        order = order[:drop] + order[drop + 1 :]

    placed = dict(zip(order, slots, strict=True))
    changes = []
    for act_id in full:
        a = acts[act_id]
        before = Slot(start=a.planned_start, end=a.planned_end)
        if act_id not in placed:
            changes.append(RecoveryChange(activity_id=act_id, op=Op.DROP, before=before))
            continue
        start, end = placed[act_id]
        after = Slot(start=min(start, MINUTES_PER_DAY - 1), end=min(end, MINUTES_PER_DAY))
        if after == before:
            op = Op.KEEP
        elif after.end - after.start > before.end - before.start:
            op = Op.EXTEND
        else:
            op = Op.MOVE
        changes.append(RecoveryChange(activity_id=act_id, op=op, before=before, after=after))

    result = tuple(changes)
    cost = compute_cost(inp, result, DEFAULT_WEIGHTS)
    return RecoveryResult(
        strategy=name,
        changes=result,
        rc_total=cost.rc_total,
        rc_breakdown=cost.breakdown,
        preservation_rate=cost.preservation_rate,
        violations=len(validate(inp, result)),
        solver_ms=0,
    )


def _latest(candidates: list[int], order: tuple[str, ...], values: dict[str, int]) -> int:
    return candidates[-1]


def _lowest_value(candidates: list[int], order: tuple[str, ...], values: dict[str, int]) -> int:
    # min over (value, -position): lowest value first; on a tie the later activity goes.
    return min(candidates, key=lambda i: (values[order[i]], -i))


def right_shift(inp: RecoveryInput) -> RecoveryResult:
    return _run(inp, "right_shift", _latest)


def greedy(inp: RecoveryInput) -> RecoveryResult:
    return _run(inp, "greedy", _lowest_value)
