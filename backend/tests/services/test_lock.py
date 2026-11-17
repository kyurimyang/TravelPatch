import pytest

from app.engine.recover import recover
from app.schemas.enums import Op, Tier, TimeRigidity
from app.services.lock import lock_in_place
from tests.engine.helpers import load_scenario_a


def _first_moved_id() -> str:
    inp = load_scenario_a()
    for result in recover(inp):
        for c in result.changes:
            if c.op == Op.MOVE:
                return c.activity_id
    raise AssertionError("scenario A should move something")


def test_locked_activity_becomes_a_must_reserved_at_its_original_time():
    inp = load_scenario_a()
    target = _first_moved_id()
    locked = lock_in_place(inp, [target])
    a = next(x for x in locked.activities if x.id == target)
    p = next(x for x in locked.preferences if x.activity_id == target)
    assert a.reservation_time == a.planned_start
    assert a.min_duration == a.planned_end - a.planned_start
    assert (p.tier, p.time_rigidity) == (Tier.MUST, TimeRigidity.RESERVED)
    # nothing else changes
    others = [x for x in locked.activities if x.id != target]
    assert others == [x for x in inp.activities if x.id != target]


def test_locked_activity_is_kept_in_place_or_the_day_is_reported_impossible():
    inp = load_scenario_a()
    target = _first_moved_id()
    results = recover(lock_in_place(inp, [target]))
    for r in results:
        c = next(c for c in r.changes if c.activity_id == target)
        assert c.op == Op.KEEP and c.before == c.after
        assert r.violations == 0


def test_unknown_activity_is_refused():
    with pytest.raises(ValueError):
        lock_in_place(load_scenario_a(), ["nope"])


def test_locking_a_later_activity_keeps_it_and_the_rest_gives_way():
    # Scenario A: a 2-hour delay moves ramen (12:50) later; locked, it stays at 12:50.
    inp = load_scenario_a()
    results = recover(lock_in_place(inp, ["ramen"]))
    assert results
    for r in results:
        ramen = next(c for c in r.changes if c.activity_id == "ramen")
        assert ramen.op == Op.KEEP and ramen.after.start == 770
        assert r.violations == 0
        assert any(c.op != Op.KEEP for c in r.changes if c.activity_id != "ramen")
