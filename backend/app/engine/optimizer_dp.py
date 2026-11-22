"""Fixed-order DP.

Walks the activities in a given order. For each one it either drops it or places it at a
(start, duration). State = (last placed activity, time it ends); per state only the cheapest
path is kept. Terms that are additive per step are optimized here: D_drop, D_shrink, D_time,
D_move. D_order is 0 for a fixed order (the outer local search adds it); D_intent is not
additive and is only evaluated afterwards by cost.compute_cost.
"""

from typing import NamedTuple

from app.engine.constraint_builder import build_constraints, solver_view
from app.engine.presets import DEFAULT_WEIGHTS, MEAL_WINDOW_MINUTES, Weights
from app.schemas.enums import Category, Op, Tier
from app.schemas.models import HOTEL_ID, Activity, Substitute
from app.schemas.recovery import RecoveryChange, RecoveryInput, Slot

STEP = 5  # minutes

# state key: (last placed activity id or None, end time)
_State = tuple[str | None, int]
# decision: None = dropped, else (start, duration, node it is placed at)
_Decision = tuple[int, int, str] | None


class _Option(NamedTuple):
    """One place an activity can go to: its original location or a substitute."""

    node: str
    open_at: int | None
    close_at: int | None
    durations: list[int]
    substitute: Substitute | None


class Solution(NamedTuple):
    changes: tuple[RecoveryChange, ...]
    cost: float


def _round_up(minutes: int) -> int:
    return -(-minutes // STEP) * STEP


def _durations(a: Activity, extend: int) -> list[int]:
    planned = a.planned_end - a.planned_start
    if extend:
        return [planned + extend]  # the user asked for exactly this much more time
    if a.reservation_time is not None:
        return [planned]  # reserved slots keep their length
    out: list[int] = []
    d = planned
    while d > a.min_duration:
        out.append(d)
        d -= STEP
    out.append(a.min_duration)
    return out


def _sub_durations(s: Substitute) -> list[int]:
    return [*range(s.duration, s.min_duration, -STEP), s.min_duration]


_Layer = dict[_State, tuple[float, tuple[_State, _Decision] | None]]


def _relax(layer: _Layer, key: _State, cost: float, back: tuple[_State, _Decision]) -> None:
    # Strict <: the first path found wins ties, so equal input gives equal output.
    if key not in layer or cost < layer[key][0]:
        layer[key] = (cost, back)


def _op(before: Slot, after: Slot) -> Op:
    if after == before:
        return Op.KEEP
    before_len, after_len = before.end - before.start, after.end - after.start
    if after_len < before_len:
        return Op.SHRINK
    if after_len > before_len:
        return Op.EXTEND
    return Op.MOVE


def solve_fixed_order(
    inp: RecoveryInput,
    order: tuple[str, ...],
    weights: Weights = DEFAULT_WEIGHTS,
    min_buffer: int = 0,
    dense_starts: bool = False,
    no_drop: frozenset[str] = frozenset(),
    reservation_buffer: int = 0,
    no_drop_categories: tuple[Category, ...] = (),
) -> Solution | None:
    """`dense_starts` tries every 5-minute start (slow): used by tests to check the pruning.

    `no_drop` lists activities that must survive (counterfactual "what if we keep X?").
    `reservation_buffer` / `no_drop_categories` are a strategy's own hard rules (presets).
    """
    inp = solver_view(inp)  # the event applied, e.g. a booking moved to its new time
    ev = inp.event
    constraints = build_constraints(inp)
    acts = {a.id: a for a in inp.activities}
    prefs = {p.activity_id: p.tier for p in inp.preferences}
    substitutability = {p.activity_id: p.substitutability for p in inp.preferences}
    table = {frozenset((t.a, t.b)): t.minutes for t in inp.travel}

    def travel(a: str, b: str) -> int:
        return 0 if a == b else table[frozenset((a, b))]

    subs_of: dict[str, list[Substitute]] = {}
    for sub in inp.substitutes:
        subs_of.setdefault(sub.replaces, []).append(sub)
    deadline = inp.day.end_deadline
    layers: list[dict[_State, tuple[float, tuple[_State, _Decision] | None]]] = [
        {(None, inp.now): (0.0, None)}
    ]

    for act_id in order:
        a = acts[act_id]
        tier = prefs[act_id]
        value = tier.weight
        planned_len = a.planned_end - a.planned_start
        extend = constraints.extension(a.id)
        in_progress = ev.location_id == a.id  # the user is there right now
        options: list[_Option] = []
        if a.id not in constraints.closed:
            options.append(_Option(a.id, a.open_at, a.close_at, _durations(a, extend), None))
        if not in_progress and extend == 0:
            options += [
                _Option(sub.id, sub.open_at, sub.close_at, _sub_durations(sub), sub)
                for sub in subs_of.get(a.id, [])
            ]
        nxt: _Layer = {}

        for state, (cost, _) in layers[-1].items():
            last, t = state
            droppable = (
                tier != Tier.MUST
                and extend == 0
                and act_id not in no_drop
                and a.category not in no_drop_categories
            )
            if droppable:  # asked-for extensions are never dropped
                drop_cost = (
                    weights.w_drop * weights.drop_factor(a.category) * value + weights.w_changed
                )
                _relax(nxt, state, cost + drop_cost, (state, None))

            origin = inp.event.location_id if last is None else last
            for opt in options:
                earliest = t + travel(origin, opt.node) + (min_buffer if last is not None else 0)
                if opt.open_at is not None:
                    earliest = max(earliest, opt.open_at)

                if in_progress:
                    # Already started: the start cannot move.
                    starts = [a.planned_start] if last is None or a.planned_start >= earliest else []
                elif opt.substitute is None and a.reservation_time is not None:
                    # A strategy may want the traveller there early (the validator re-checks).
                    ready = max(earliest, t + travel(origin, opt.node) + reservation_buffer)
                    starts = [a.reservation_time] if a.reservation_time >= ready else []
                else:
                    s0 = _round_up(earliest)
                    if dense_starts:
                        starts = list(range(s0, deadline, STEP))
                    else:
                        # A later start only adds D_time and delay, except between s0 and the
                        # planned start: there, waiting trades D_time against how tight the
                        # following activities become, so every step in between can be optimal.
                        starts = [*range(s0, a.planned_start, STEP), max(s0, a.planned_start)]
                booked = opt.substitute is None and a.reservation_time is not None
                if a.category == Category.MEAL and not booked:
                    # Hard: a meal (or its substitute) starts near when it was planned (A3).
                    # None left -> only dropping it remains, never lunch at 17:00. A booked
                    # meal is pinned by its booking instead, which the user chose.
                    starts = [s for s in starts if abs(s - a.planned_start) <= MEAL_WINDOW_MINUTES]

                # A substitution is paid by D_sub (not D_shrink) and always counts as a change.
                sub_cost = (
                    weights.w_sub * (value * (1 - substitutability[a.id]) + opt.substitute.penalty)
                    if opt.substitute is not None
                    else 0.0
                )
                for s in starts:
                    for d in opt.durations:
                        cap = constraints.duration_cap(a.id)
                        if cap is not None and d > cap:
                            continue  # too tiring
                        end = s + d
                        if end > deadline or (opt.close_at is not None and end > opt.close_at):
                            continue
                        if in_progress and end < inp.now:
                            continue  # cannot have ended in the past
                        if a.outdoor and constraints.rain is not None:
                            rain_start, rain_end = constraints.rain
                            if s < rain_end and end > rain_start:
                                continue  # outdoors during rain
                        if opt.substitute is not None:
                            step = weights.w_changed + sub_cost
                        else:
                            step = (
                                weights.w_shrink * value * max(0, planned_len - d) / planned_len
                                + (weights.w_changed if (s, end) != (a.planned_start, a.planned_end) else 0.0)
                            )
                        step += weights.w_time * abs(s - a.planned_start) / 60 + (
                            weights.w_move * travel(last, opt.node) / 60 if last is not None else 0.0
                        )
                        _relax(nxt, (opt.node, end), cost + step, (state, (s, d, opt.node)))
        layers.append(nxt)

    # Final: the last placed activity must still leave time to get back to the hotel.
    finals = [
        (cost, t, last or "", state)
        for state, (cost, _) in layers[-1].items()
        for last, t in [state]
        if last is None or t + travel(last, HOTEL_ID) <= deadline
    ]
    if not finals:
        return None
    best_cost, _, _, state = min(finals, key=lambda f: f[:3])

    decisions: dict[str, _Decision] = {}
    for i in range(len(order), 0, -1):
        _, back = layers[i][state]
        assert back is not None
        state, decisions[order[i - 1]] = back

    changes = []
    for act_id in order:
        a = acts[act_id]
        before = Slot(start=a.planned_start, end=a.planned_end)
        dec = decisions[act_id]
        if dec is None:
            changes.append(RecoveryChange(activity_id=act_id, op=Op.DROP, before=before))
        else:
            after = Slot(start=dec[0], end=dec[0] + dec[1])
            if dec[2] != act_id:
                changes.append(
                    RecoveryChange(
                        activity_id=act_id,
                        op=Op.SUBSTITUTE,
                        before=before,
                        after=after,
                        substitute_id=dec[2],
                    )
                )
            else:
                changes.append(
                    RecoveryChange(activity_id=act_id, op=_op(before, after), before=before, after=after)
                )
    return Solution(tuple(changes), best_cost)
