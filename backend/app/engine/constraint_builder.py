"""Rule table: user event -> constraints the DP must respect.

LLM output never reaches the solver directly; it goes through the typed event and then
through this file. The validator does NOT import this module: it reads the event again on
its own, so a mistake here cannot hide itself.
"""

from math import ceil

from app.schemas.events import ExtendEvent, FatigueEvent, WeatherEvent
from app.schemas.models import MINUTES_PER_DAY, _Frozen
from app.schemas.recovery import RecoveryInput


class Constraints(_Frozen):
    # Outdoor activities must not overlap [start, end) of the rain.
    rain: tuple[int, int] | None = None
    # (activity id, extra minutes) the user asked for.
    extensions: tuple[tuple[str, int], ...] = ()
    # (activity id, longest allowed duration in minutes), from tiredness.
    duration_caps: tuple[tuple[str, int], ...] = ()

    def extension(self, activity_id: str) -> int:
        return dict(self.extensions).get(activity_id, 0)

    def duration_cap(self, activity_id: str) -> int | None:
        return dict(self.duration_caps).get(activity_id)


def build_constraints(inp: RecoveryInput) -> Constraints:
    ev = inp.event
    if isinstance(ev, WeatherEvent):
        end = ev.end_time if ev.end_time is not None else MINUTES_PER_DAY
        return Constraints(rain=(ev.start_time, end))
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
