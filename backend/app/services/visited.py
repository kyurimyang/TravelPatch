"""Places the traveller has already visited, taken out before the engine runs (2026-11-22).

Recovering in the middle of the day with the morning still in the plan made the engine read
the visited places as missed: dropped, or no plan at all when one was must (review 2026-11-19,
A1). They are not at stake, so they leave the input and the preservation rate's denominator.

The user ticks them on Recover (pre-ticked by the app when they ended before now). A visited
place the user is still standing at is over but is where the rest of the day starts: it
becomes the start node, which the engine reads only as a node of the travel table (the
arrival airport used it before; by now the day no longer starts there).

Pure and deterministic, like the engine; it lives here because what is "left of the day" is a
fact about the trip, not part of the optimisation (decision 2026-11-22). Moved from the
frontend so the eval, the API and the app share one rule.
"""

from collections.abc import Iterable

from app.schemas.models import START_ID
from app.schemas.recovery import RecoveryInput


class VisitedError(ValueError):
    """The visited list names something that is not an activity, or what the event is about."""


def apply_visited(inp: RecoveryInput, visited: Iterable[str]) -> RecoveryInput:
    gone = set(visited)
    if not gone:
        return inp
    ids = {a.id for a in inp.activities}
    unknown = sorted(gone - ids)
    if unknown:
        raise VisitedError(f"not activities of this day: {unknown}")
    target = getattr(inp.event, "activity_id", None)
    if target in gone:
        raise VisitedError(f"the event is about {target}: it cannot be visited already")

    data = inp.model_dump()
    travel = data["travel"]
    here = inp.event.location_id
    if here in gone:
        # Over, but the rest of the day starts from its place.
        spot = next(a for a in inp.activities if a.id == here)
        data["day"] |= {"start_lat": spot.lat, "start_lng": spot.lng}
        travel = [
            {**t, "a": START_ID if t["a"] == here else t["a"], "b": START_ID if t["b"] == here else t["b"]}
            for t in travel
            if START_ID not in (t["a"], t["b"])
        ]
        data["event"]["location_id"] = START_ID

    subs_gone = {s.id for s in inp.substitutes if s.replaces in gone}
    out_nodes = gone | subs_gone
    data["activities"] = [a for a in data["activities"] if a["id"] not in gone]
    data["preferences"] = [p for p in data["preferences"] if p["activity_id"] not in gone]
    data["substitutes"] = [s for s in data["substitutes"] if s["id"] not in subs_gone]
    data["travel"] = [t for t in travel if t["a"] not in out_nodes and t["b"] not in out_nodes]
    return RecoveryInput.model_validate(data)
