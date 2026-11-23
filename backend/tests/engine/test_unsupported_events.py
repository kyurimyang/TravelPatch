from app.engine.counterfactual import restore
from app.engine.recover import recover
from app.engine.validator import validate
from app.schemas.enums import Op
from tests.engine.helpers import scenario_a_with_unsupported_event

# Every event type is solved now: RESERVATION_CHANGE since 2026-11-22 (scenario F), MUST_VISIT
# since 2026-11-23. The guard in candidate.py stays for any type added to the schema later.


def test_reservation_change_is_solved_now() -> None:
    results = recover(scenario_a_with_unsupported_event("RESERVATION_CHANGE"))
    assert results
    assert all(r.violations == 0 for r in results)


def test_a_must_visit_place_is_placed_once_never_dropped_and_validated() -> None:
    inp = scenario_a_with_unsupported_event("MUST_VISIT")
    results = recover(inp)
    assert results
    for r in results:
        added = [c for c in r.changes if c.activity_id == "new1"]
        assert len(added) == 1
        c = added[0]
        assert c.op == Op.ADD and c.before is None and c.after is not None
        assert c.after.end - c.after.start >= 30  # its min_duration
        assert c.after.start >= inp.now
        assert validate(inp, r.changes) == []
        # Every planned piece still has exactly one entry.
        assert sorted(x.activity_id for x in r.changes) == sorted(
            [a.id for a in inp.activities] + ["new1"]
        )


def test_adding_a_place_and_asking_to_keep_a_dropped_one_work_together() -> None:
    inp = scenario_a_with_unsupported_event("MUST_VISIT")
    for r in recover(inp):
        for c in r.changes:
            if c.op == Op.DROP:
                cf = restore(inp, r, c.activity_id)
                if cf is not None:
                    kept = {x.activity_id: x for x in cf.result.changes}
                    assert kept[c.activity_id].op != Op.DROP and kept["new1"].op == Op.ADD


def test_an_added_place_is_not_put_before_the_day_begins() -> None:
    # Asked just after midnight (00:16), the place used to go at 00:45 (2026-11-24).
    inp = scenario_a_with_unsupported_event("MUST_VISIT")
    late_night = inp.model_validate(
        {**inp.model_dump(), "event": {**inp.event.model_dump(), "occurred_at": 16}}
    )
    for r in recover(late_night):
        added = next(c for c in r.changes if c.activity_id == "new1")
        assert added.after.start >= late_night.day.start_time
