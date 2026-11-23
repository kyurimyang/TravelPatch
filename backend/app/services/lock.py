""" "Leave this piece as it was" (고정하기), without touching the engine.

A locked activity is turned into what the engine already knows how to hold still: a must that
is reserved at its original start, with no shortening. The solver can then neither move, shrink
nor drop it, and the validator checks it like any reservation. If that makes the day impossible
(e.g. its time has already passed), recover() comes back empty and the blockers say why.
"""

from collections.abc import Iterable

from app.schemas.enums import Tier, TimeRigidity
from app.schemas.recovery import RecoveryInput


def lock_in_place(inp: RecoveryInput, activity_ids: Iterable[str]) -> RecoveryInput:
    ids = set(activity_ids)
    unknown = ids - {a.id for a in inp.activities}
    if unknown:
        raise ValueError(f"unknown activity: {sorted(unknown)}")
    # The piece the user asked more time at: "as it was" would contradict the request, and the
    # extension wins in the solver anyway, so the lock would silently not hold.
    if inp.event.type == "EXTEND" and inp.event.activity_id in ids:
        raise ValueError(f"cannot lock the activity being extended: {inp.event.activity_id}")
    data = inp.model_dump()
    for a in data["activities"]:
        if a["id"] in ids:
            a["reservation_time"] = a["planned_start"]
            a["min_duration"] = a["planned_end"] - a["planned_start"]
    for p in data["preferences"]:
        if p["activity_id"] in ids:
            p["tier"] = Tier.MUST
            p["time_rigidity"] = TimeRigidity.RESERVED
    return RecoveryInput.model_validate(data)
