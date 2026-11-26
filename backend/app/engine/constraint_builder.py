"""Rule table: user events -> constraints the DP must respect.

LLM output never reaches the solver directly; it goes through the typed events and then
through this file. Several events stack (decision 2026-11-26): each adds its own rules and
none replaces another's. The validator does NOT import this module: it reads the events
again on its own, so a mistake here cannot hide itself.
"""

from math import ceil

from app.schemas.enums import Tier, TimeRigidity, Wish
from app.schemas.events import (
    ClosureEvent,
    ExtendEvent,
    FatigueEvent,
    MustVisitEvent,
    ReservationChangeEvent,
    WaitEvent,
    WeatherEvent,
)
from app.schemas.models import MINUTES_PER_DAY, Activity, Preference, _Frozen
from app.schemas.recovery import RecoveryInput


class Constraints(_Frozen):
    # Outdoor activities must not overlap any [start, end) of rain (one per WEATHER event).
    rains: tuple[tuple[int, int], ...] = ()
    # (activity id, extra minutes) the user asked for.
    extensions: tuple[tuple[str, int], ...] = ()
    # (activity id, longest allowed duration in minutes), from tiredness (tightest cap wins).
    duration_caps: tuple[tuple[str, int], ...] = ()
    # Activities that cannot stay at their original place (closed).
    closed: tuple[str, ...] = ()
    # (activity id, queue minutes) at its own place, before the activity itself (WAIT).
    waits: tuple[tuple[str, int], ...] = ()
    # "실내 우선": outdoor time costs D_outdoor (soft, never a hard rule).
    outdoor_cost: bool = False

    def extension(self, activity_id: str) -> int:
        return dict(self.extensions).get(activity_id, 0)

    def duration_cap(self, activity_id: str) -> int | None:
        return dict(self.duration_caps).get(activity_id)

    def wait(self, activity_id: str) -> int:
        return dict(self.waits).get(activity_id, 0)

    def rained_on(self, start: int, end: int) -> bool:
        return any(start < r_end and end > r_start for r_start, r_end in self.rains)


def solver_view(inp: RecoveryInput) -> RecoveryInput:
    """The input as the solver should see it once the event is applied.

    RESERVATION_CHANGE: the booked activity's reservation_time becomes the new time, so every
    reader of reservation_time (DP, conflict explanation) follows it. planned_start stays: the
    original plan is what the change is measured against. The validator never sees this view;
    it reads the event itself (module docstring)."""
    ev = inp.event
    if isinstance(ev, MustVisitEvent):
        inp = inp.model_copy(
            update={
                "activities": (*inp.activities, added_activity(inp)),
                "preferences": (
                    *inp.preferences,
                    Preference(
                        activity_id=ev.activity_id,
                        tier=Tier.MUST,
                        substitutability=0.0,
                        time_rigidity=TimeRigidity.FLEXIBLE,
                    ),
                ),
            }
        )
    moved = {e.activity_id: e.new_time for e in inp.events if isinstance(e, ReservationChangeEvent)}
    if not moved:
        return inp
    activities = tuple(
        a.model_copy(update={"reservation_time": moved[a.id]}) if a.id in moved else a
        for a in inp.activities
    )
    return inp.model_copy(update={"activities": activities})


def added_activity(inp: RecoveryInput) -> Activity:
    """MUST_VISIT: the new place as an activity the solver can place (decision 2026-11-23). It has
    no planned slot; "planned" is as soon as possible from now, for its full length, so the DP's
    start and length rules apply as to any piece. Its time cost is not counted (optimizer_dp)."""
    ev = inp.event
    assert isinstance(ev, MustVisitEvent)
    # Not before the day begins: asked at 00:16, the place went at 00:45 (found 2026-11-24).
    # Planned pieces keep their own times; only the new one has none, so it gets the day's start
    # as its earliest opening. The validator checks the place's real hours on its own.
    day_start = inp.day.start_time
    opens = max(ev.open_at, day_start) if ev.open_at is not None else day_start
    start = min(max(inp.now, day_start), MINUTES_PER_DAY - ev.duration)
    return Activity(
        id=ev.activity_id,
        title=ev.title,
        category=ev.category,
        lat=ev.lat,
        lng=ev.lng,
        planned_start=start,
        planned_end=start + ev.duration,
        min_duration=ev.min_duration,
        outdoor=None,
        walking=None,
        open_at=opens,
        close_at=ev.close_at,
    )


def _fatigue_caps(inp: RecoveryInput, ev: FatigueEvent) -> dict[str, int]:
    caps: dict[str, int] = {}
    for a in inp.activities:
        # Reserved slots cannot shrink; the activity the user is in is already running.
        if a.walking and a.reservation_time is None and a.id != ev.location_id:
            planned = a.planned_end - a.planned_start
            caps[a.id] = max(a.min_duration, ceil(planned * ev.walking_ratio / 5) * 5)
    return caps


def build_constraints(inp: RecoveryInput) -> Constraints:
    rains: list[tuple[int, int]] = []
    closed: set[str] = set()
    extensions: dict[str, int] = {}
    waits: dict[str, int] = {}
    caps: dict[str, int] = {}
    for ev in inp.events:
        if isinstance(ev, WeatherEvent):
            end = ev.end_time if ev.end_time is not None else MINUTES_PER_DAY
            rains.append((ev.start_time, end))
        elif isinstance(ev, ClosureEvent):
            closed.add(ev.activity_id)
        elif isinstance(ev, ExtendEvent):
            extensions[ev.activity_id] = ev.extra_minutes
        elif isinstance(ev, WaitEvent):
            waits[ev.activity_id] = ev.minutes
        elif isinstance(ev, FatigueEvent):
            for aid, cap in _fatigue_caps(inp, ev).items():
                caps[aid] = min(cap, caps.get(aid, cap))
    # Sorted everywhere: equal input gives equal constraints whatever the event order.
    return Constraints(
        rains=tuple(sorted(set(rains))),
        extensions=tuple(sorted(extensions.items())),
        duration_caps=tuple(sorted(caps.items())),
        closed=tuple(sorted(closed)),
        waits=tuple(sorted(waits.items())),
        outdoor_cost=Wish.INDOOR in inp.wishes,
    )
