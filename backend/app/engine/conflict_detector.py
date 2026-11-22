"""Name the hard constraints that make a day impossible to recover.

Pure and independent of the solver: it reads the input only. Everything reported is certain
(a reported blocker means no valid plan exists); anything it cannot prove is left out, so an
empty result means "no single cause found", not "solvable". Only activities that cannot be
dropped can block: must tier, or the one the user asked to extend.
"""

from itertools import pairwise

from app.engine.constraint_builder import solver_view
from app.engine.presets import MEAL_WINDOW_MINUTES
from app.schemas.enums import Category, Tier
from app.schemas.events import ClosureEvent, ExtendEvent, WeatherEvent
from app.schemas.models import HOTEL_ID, MINUTES_PER_DAY, Activity
from app.schemas.recovery import Blocker, RecoveryInput

STEP = 5


def find_blockers(inp: RecoveryInput) -> list[Blocker]:
    inp = solver_view(inp)  # a moved booking is explained at its new time
    ev = inp.event
    table = {frozenset((t.a, t.b)): t.minutes for t in inp.travel}

    def travel(a: str, b: str) -> int:
        return 0 if a == b else table[frozenset((a, b))]

    musts = {p.activity_id for p in inp.preferences if p.tier == Tier.MUST}
    extended = ev.activity_id if isinstance(ev, ExtendEvent) else None
    out: list[Blocker] = []

    for a in sorted(inp.activities, key=lambda a: a.id):
        if (a.id not in musts and a.id != extended) or a.reservation_time is None:
            continue
        if a.id == ev.location_id:
            continue  # the user is already there
        r = a.reservation_time
        if r < inp.now + travel(ev.location_id, a.id):
            out.append(Blocker(kind="reserved_in_past", activity_id=a.id, blocking_time=r))
        elif isinstance(ev, WeatherEvent) and a.outdoor is True:  # unknown (None) is not blocked
            rain_end = ev.end_time if ev.end_time is not None else MINUTES_PER_DAY
            if r < rain_end and r + (a.planned_end - a.planned_start) > ev.start_time:
                out.append(Blocker(kind="reserved_in_rain", activity_id=a.id, blocking_time=r))

    # Closed, cannot be dropped, and nothing to stand in for it: no plan can exist.
    # With any substitute it is not certain (one may fit), so nothing is reported then.
    if (
        isinstance(ev, ClosureEvent)
        and ev.activity_id in musts
        and not any(s.replaces == ev.activity_id for s in inp.substitutes)
    ):
        out.append(Blocker(kind="closed_no_substitute", activity_id=ev.activity_id))

    out += _reservation_clashes(inp, musts, extended, travel)
    out += _meals_out_of_reach(inp, musts, travel)

    if isinstance(ev, ExtendEvent):
        target = next(a for a in inp.activities if a.id == ev.activity_id)
        most = _max_extra(inp, target, travel)
        if most < ev.extra_minutes:
            out.append(
                Blocker(kind="extension_blocked", activity_id=target.id, max_extra_minutes=most)
            )
    return out


def _max_extra(inp: RecoveryInput, a: Activity, travel) -> int:
    """Upper bound on the extension: ignores other activities, so a shortfall is certain."""
    ev = inp.event
    planned = a.planned_end - a.planned_start
    if ev.location_id == a.id:
        start = a.planned_start  # already started: the start cannot move
    elif a.reservation_time is not None:
        start = a.reservation_time
    else:
        start = max(inp.now + travel(ev.location_id, a.id), a.open_at or 0)
    latest_end = inp.day.end_deadline - travel(a.id, HOTEL_ID)
    if a.close_at is not None:
        latest_end = min(latest_end, a.close_at)
    return max(0, (latest_end - start - planned) // STEP * STEP)


def _reservation_clashes(
    inp: RecoveryInput, musts: set[str], extended: str | None, travel
) -> list[Blocker]:
    """Two bookings that can neither move nor be dropped, too close for the first to end and the
    traveller to get to the second. Reserved slots keep their length, so this is certain."""
    ev = inp.event
    pinned = sorted(
        (
            a
            for a in inp.activities
            if a.reservation_time is not None and (a.id in musts or a.id == extended)
        ),
        key=lambda a: (a.reservation_time, a.id),
    )
    out: list[Blocker] = []
    for first, second in pairwise(pinned):
        length = first.planned_end - first.planned_start
        if isinstance(ev, ExtendEvent) and ev.activity_id == first.id:
            length += ev.extra_minutes
        if first.reservation_time + length + travel(first.id, second.id) > second.reservation_time:
            out.append(
                Blocker(
                    kind="reservations_clash",
                    activity_id=second.id,
                    blocking_time=second.reservation_time,
                )
            )
    return out


def _meals_out_of_reach(inp: RecoveryInput, musts: set[str], travel) -> list[Blocker]:
    """A must meal (not booked, not under way, nothing to replace it) whose earliest possible
    start is past the end of its window: dropping is forbidden and no start is allowed."""
    ev = inp.event
    replaced = {s.replaces for s in inp.substitutes}
    out: list[Blocker] = []
    for a in sorted(inp.activities, key=lambda a: a.id):
        if (
            a.category != Category.MEAL
            or a.id not in musts
            or a.reservation_time is not None
            or a.id == ev.location_id
            or a.id in replaced
        ):
            continue
        earliest = -(-max(inp.now + travel(ev.location_id, a.id), a.open_at or 0) // STEP) * STEP
        latest = a.planned_start + MEAL_WINDOW_MINUTES
        if earliest > latest:
            out.append(Blocker(kind="meal_out_of_reach", activity_id=a.id, blocking_time=latest))
    return out
