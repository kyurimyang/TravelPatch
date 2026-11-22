import json
from pathlib import Path

import pytest

from app.engine.local_search import improve_order
from app.engine.presets import STRATEGIES
from app.engine.recover import original_order, recover, solve_candidate
from app.engine.validator import validate
from app.schemas.recovery import RecoveryInput
from tests.engine.helpers import load_scenario_a

SCENARIOS = Path(__file__).parents[1] / "scenarios"
BALANCED = next(s for s in STRATEGIES if s.name == "balanced")


def _load(name: str) -> RecoveryInput:
    raw = json.loads((SCENARIOS / name).read_text(encoding="utf-8"))
    raw.pop("expected", None)
    return RecoveryInput.model_validate(raw)


def _base(inp: RecoveryInput):
    result = solve_candidate(inp, BALANCED, original_order(inp))
    assert result is not None
    return result


def test_keeps_the_original_order_when_no_swap_pays_off() -> None:
    inp = load_scenario_a()
    base = _base(inp)
    assert improve_order(inp, BALANCED, base) == base


def test_a_swap_that_cuts_rc_by_ten_percent_is_adopted() -> None:
    # A 43% cheaper plan exists after swapping two neighbours (measured on this scenario).
    # Was i07_delay until the meal window (2026-11-19): its better order put lunch 145 min late.
    inp = _load("eval50/i00_delay.json")
    base = _base(inp)
    better = improve_order(inp, BALANCED, base, max_tries=99)
    assert better.rc_total <= base.rc_total * 0.9
    assert better.rc_breakdown.d_order >= 1  # the order really changed
    assert better.violations == 0
    assert validate(inp, better.changes, BALANCED.min_buffer) == []


def test_threshold_blocks_small_gains() -> None:
    inp = _load("eval50/i07_delay.json")
    base = _base(inp)
    assert improve_order(inp, BALANCED, base, max_tries=99, min_gain=0.99) == base


def test_zero_tries_does_nothing() -> None:
    inp = _load("eval50/i07_delay.json")
    base = _base(inp)
    assert improve_order(inp, BALANCED, base, max_tries=0) == base


def test_changes_stay_in_the_original_order() -> None:
    inp = _load("eval50/i07_delay.json")
    better = improve_order(inp, BALANCED, _base(inp), max_tries=99)
    assert tuple(c.activity_id for c in better.changes) == original_order(inp)


def test_recover_can_switch_the_search_off() -> None:
    inp = _load("eval50/i00_delay.json")
    plain = {r.strategy: r for r in recover(inp, max_tries=0)}
    searched = {r.strategy: r for r in recover(inp, max_tries=99)}
    assert searched["balanced"].rc_total < plain["balanced"].rc_total
    assert all(r.violations == 0 for r in searched.values())


def test_deterministic() -> None:
    inp = _load("eval50/i07_delay.json")
    assert recover(inp) == recover(inp)


@pytest.mark.parametrize("name", ["scenario_a.json", "scenario_b.json", "scenario_e.json"])
def test_scenario_results_stay_valid_with_search_on(name: str) -> None:
    inp = _load(name)
    for r in recover(inp):
        assert r.violations == 0
