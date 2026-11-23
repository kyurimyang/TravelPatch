"""Rule table: user event -> constraints the DP must respect.

LLM output never reaches the solver directly; it goes through the typed event and then
through this file. The validator does NOT import this module: it reads the event again on
its own, so a mistake here cannot hide itself.
"""

from math import ceil

from app.schemas.enums import Tier, TimeRigidity
from app.schemas.events import (
    ClosureEvent,
    ExtendEvent,
    FatigueEvent,
    MustVisitEvent,
    ReservationChangeEvent,
    WeatherEvent,
)
from app.schemas.models import MINUTES_PER_DAY, Activity, Preference, _Frozen
from app.schemas.recovery import RecoveryInput


class Constraints(_Frozen):
    # Outdoor activities must not overlap [start, end) of the rain.
    rain: tuple[int, int] | None = None
    # (activity id, extra minutes) the user asked for.
    extensions: tuple[tuple[str, int], ...] = ()
    # (activity id, longest allowed duration in minutes), from tiredness.
    duration_caps: tuple[tuple[str, int], ...] = ()
    # Activities that cannot stay at their original place (closed).
    closed: tuple[str, ...] = ()

    def extension(self, activity_id: str) -> int:
        return dict(self.extensions).get(activity_id, 0)

    def duration_cap(self, activity_id: str) -> int | None:
        return dict(self.duration_caps).get(activity_id)


def solver_view(inp: RecoveryInput) -> RecoveryInput:
    """The input as the solver should see it once the event is applied.

    RESERVATION_CHANGE: the booked activity's reservation_time becomes the new time, so every
    reader of reservation_time (DP, conflict explanation) follows it. planned_start stays: the
    original plan is what the change is measured against. The validator never sees this view;
    it reads the event itself (module docstring)."""
    ev = inp.event
    if isinstance(ev, MustVisitEvent):
        return inp.model_copy(
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
    if not isinstance(ev, ReservationChangeEvent):
        return inp
    activities = tuple(
        a.model_copy(update={"reservation_time": ev.new_time}) if a.id == ev.activity_id else a
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


def build_constraints(inp: RecoveryInput) -> Constraints:
    ev = inp.event
    if isinstance(ev, WeatherEvent):
        end = ev.end_time if ev.end_time is not None else MINUTES_PER_DAY
        return Constraints(rain=(ev.start_time, end))
    if isinstance(ev, ClosureEvent):
        return Constraints(closed=(ev.activity_id,))
    if isinstance(ev, ExtendEvent):
        return Constraints(extensions=((ev.activity_id, ev.extra_minutes),))
    if isinstance(ev, FatigueEvent):
        caps = []
        for a in sorted(inp.activities, key=lambda a: a.id):
            # Reserved slots cannot shrink; the activity the user is in is already running.
            if a.walking and a.reservation_time is None and a.id != ev.location_id:
                planned = a.planned_end - a.planned_start
                caps.append((a.id, max(a.min_duration, ceil(planned * ev.walking_ratio / 5) * 5)))
        return Constraints(duration_caps=tuple(caps))
    return Constraints()
