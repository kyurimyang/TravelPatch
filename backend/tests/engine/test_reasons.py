import json
from pathlib import Path

import pytest

from app.engine.recover import recover
from app.schemas.enums import Op, ReasonType
from app.schemas.recovery import RecoveryChange, RecoveryInput, RecoveryResult
from tests.engine.helpers import load_scenario_a

SCENARIOS = Path(__file__).parents[1] / "scenarios"


def _candidate(inp: RecoveryInput, strategy: str) -> RecoveryResult:
    return next(r for r in recover(inp) if r.strategy == strategy)


def _change(result: RecoveryResult, activity_id: str) -> RecoveryChange:
    return next(c for c in result.changes if c.activity_id == activity_id)


def _weight(inp: RecoveryInput, activity_id: str) -> int:
    return next(p.tier.weight for p in inp.preferences if p.activity_id == activity_id)


def test_kept_activities_have_no_reason() -> None:
    for result in recover(load_scenario_a()):
        for c in result.changes:
            if c.op == Op.KEEP:
                assert c.reason_type is None
                assert c.reason_data is None


def test_a_move_forced_by_the_delay_is_binding_on_the_past() -> None:
    # The user can only start at 11:00; meiji was planned for 9:20.
    change = _change(_candidate(load_scenario_a(), "balanced"), "meiji")
    assert change.op == Op.MOVE
    assert change.reason_type == ReasonType.BINDING
    assert change.reason_data is not None
    assert change.reason_data.forced_by == ("past",)


def test_a_ripple_move_is_binding_on_travel_time() -> None:
    # ramen only moves because the activities before it moved: its own slot is fine.
    change = _change(_candidate(load_scenario_a(), "balanced"), "ramen")
    assert change.op == Op.MOVE
    assert change.reason_type == ReasonType.BINDING
    assert change.reason_data is not None
    assert change.reason_data.forced_by == ("travel",)


def test_a_shrink_is_a_value_choice_with_its_numbers() -> None:
    inp = load_scenario_a()
    c = _change(_candidate(inp, "balanced"), "omotesando")
    assert c.op == Op.SHRINK
    assert c.before is not None and c.after is not None
    assert c.reason_type == ReasonType.VALUE
    d = c.reason_data
    assert d is not None
    before_len, after_len = c.before.end - c.before.start, c.after.end - c.after.start
    assert d.forced_by == ()
    assert d.value == _weight(inp, "omotesando")
    assert d.minutes_saved == before_len - after_len
    # Same formula as cost.py's D_shrink: value x (minutes cut / original minutes).
    assert d.value_lost == pytest.approx(d.value * (before_len - after_len) / before_len)


def test_a_drop_loses_the_whole_value_and_frees_the_whole_slot() -> None:
    inp = load_scenario_a()
    c = _change(_candidate(inp, "relaxed"), "omotesando")
    assert c.op == Op.DROP
    assert c.before is not None
    assert c.reason_type == ReasonType.VALUE
    d = c.reason_data
    assert d is not None
    assert d.value_lost == _weight(inp, "omotesando")
    assert d.minutes_saved == c.before.end - c.before.start


def test_a_closed_place_is_binding_on_the_closure() -> None:
    raw = json.loads((SCENARIOS / "eval50/i00_closure.json").read_text(encoding="utf-8"))
    raw.pop("expected", None)
    inp = RecoveryInput.model_validate(raw)
    target = inp.event.activity_id  # type: ignore[union-attr]
    candidates = recover(inp)
    assert candidates
    for result in candidates:
        c = _change(result, target)
        assert c.op in (Op.DROP, Op.SUBSTITUTE)
        assert c.reason_type == ReasonType.BINDING
        assert c.reason_data is not None
        assert "closure" in c.reason_data.forced_by


def test_reasons_never_change_the_plan_itself() -> None:
    # The classifier only reads; slots and ops must be what the solver chose.
    inp = load_scenario_a()
    for result in recover(inp, max_tries=0):
        assert result.violations == 0
        for c in result.changes:
            assert (c.before is None) == (c.op == Op.ADD)
            assert (c.after is None) == (c.op == Op.DROP)
