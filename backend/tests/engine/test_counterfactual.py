import pytest

from app.engine.counterfactual import restore
from app.engine.recover import recover
from app.engine.validator import validate
from app.schemas.enums import Op
from app.schemas.recovery import RecoveryInput, RecoveryResult
from tests.engine.helpers import load_scenario_a


def _candidate(inp: RecoveryInput, strategy: str) -> RecoveryResult:
    return next(r for r in recover(inp) if r.strategy == strategy)


def test_restoring_a_dropped_activity_keeps_it_and_stays_valid() -> None:
    inp = load_scenario_a()
    base = _candidate(inp, "relaxed")  # drops omotesando and shibuya_shop
    assert "omotesando" in {c.activity_id for c in base.changes if c.op == Op.DROP}

    cf = restore(inp, base, "omotesando")
    assert cf is not None
    by_id = {c.activity_id: c for c in cf.result.changes}
    assert by_id["omotesando"].op != Op.DROP
    assert cf.result.strategy == base.strategy
    assert cf.result.violations == 0
    # the plan still passes the independent validator under the strategy's own buffer
    assert validate(inp, cf.result.changes, min_buffer=20) == []


def test_restoring_costs_something_and_reports_what_else_changed() -> None:
    inp = load_scenario_a()
    base = _candidate(inp, "relaxed")
    cf = restore(inp, base, "omotesando")
    assert cf is not None
    # Same strategy, same weights: the base was the cheapest plan, forcing a keep cannot beat it.
    assert cf.d_rc >= -1e-9
    # The sign of the preservation change is not fixed: squeezing the others to fit X can cost
    # more than X is worth. That is exactly what the user needs to be told.
    assert cf.d_preservation == pytest.approx(cf.result.preservation_rate - base.preservation_rate)
    base_by_id = {c.activity_id: c for c in base.changes}
    new_by_id = {c.activity_id: c for c in cf.result.changes}
    assert "omotesando" not in {e.activity_id for e in cf.side_effects}  # X itself is not a side effect
    for e in cf.side_effects:
        assert e.before == base_by_id[e.activity_id]
        assert e.after == new_by_id[e.activity_id]
        assert e.before != e.after
    changed = {i for i in base_by_id if i != "omotesando" and base_by_id[i] != new_by_id[i]}
    assert {e.activity_id for e in cf.side_effects} == changed
    assert [e.activity_id for e in cf.side_effects] == sorted(changed)  # deterministic order


def test_activity_that_is_already_kept_cannot_be_restored() -> None:
    inp = load_scenario_a()
    base = _candidate(inp, "balanced")
    with pytest.raises(ValueError):
        restore(inp, base, "meiji")


def test_none_when_keeping_it_makes_the_day_impossible() -> None:
    inp = load_scenario_a()
    # The shop closes at 10:00, before the delayed user can move at 11:00: it can only be dropped.
    shop = next(a for a in inp.activities if a.id == "shibuya_shop")
    closed = inp.model_copy(
        update={
            "activities": tuple(
                a.model_copy(update={"close_at": 600}) if a.id == shop.id else a for a in inp.activities
            )
        }
    )
    base = _candidate(closed, "balanced")
    assert any(c.activity_id == "shibuya_shop" and c.op == Op.DROP for c in base.changes)
    assert restore(closed, base, "shibuya_shop") is None


def test_deterministic() -> None:
    inp = load_scenario_a()
    base = _candidate(inp, "relaxed")
    assert restore(inp, base, "omotesando") == restore(inp, base, "omotesando")
