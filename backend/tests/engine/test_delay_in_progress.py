from app.engine.recover import recover
from app.schemas.enums import Op, Tier
from tests.engine.helpers import load_scenario_a


def test_a_delay_inside_a_must_keeps_the_user_there_until_they_can_move() -> None:
    # Found 2026-11-23 in the flow test: at a must in progress, a delay past its planned end left
    # only "drop it", which a must forbids, so no plan existed at all.
    inp = load_scenario_a()
    first = min(inp.activities, key=lambda a: a.planned_start)
    prefs = tuple(
        p.model_copy(update={"tier": Tier.MUST}) if p.activity_id == first.id else p
        for p in inp.preferences
    )
    move_at = first.planned_end + 30
    event = {
        "type": "DELAY",
        "occurred_at": first.planned_start + 10,
        "start_time": move_at,
        "location_id": first.id,
    }
    delayed = inp.model_validate({**inp.model_dump(), "preferences": prefs, "event": event})
    results = recover(delayed)
    assert results
    for r in results:
        here = next(c for c in r.changes if c.activity_id == first.id)
        assert here.op == Op.EXTEND
        assert here.after.start == first.planned_start and here.after.end >= move_at
        assert r.violations == 0
