import pytest

from app.engine.cost import compute_cost
from app.engine.presets import DEFAULT_WEIGHTS, STRATEGIES
from app.engine.recover import recover
from tests.engine.helpers import load_scenario_a, original_plan, plan


def test_strategy_names_are_unique_and_balanced_is_first() -> None:
    names = [s.name for s in STRATEGIES]
    assert len(set(names)) == len(names)
    assert names[0] == "balanced"
    assert STRATEGIES[0].weights == DEFAULT_WEIGHTS


def test_sightseeing_preset_doubles_the_drop_cost_of_sightseeing() -> None:
    inp = load_scenario_a()
    sightseeing = next(s for s in STRATEGIES if s.name == "sightseeing").weights
    # omotesando is sightseeing with value 1: dropping it costs 1.0 more under this preset
    changes = plan(inp, base=original_plan(inp), omotesando=None)
    base = compute_cost(inp, changes, DEFAULT_WEIGHTS)
    boosted = compute_cost(inp, changes, sightseeing)
    assert boosted.rc_total - base.rc_total == pytest.approx(1.0)
    assert boosted.breakdown == base.breakdown  # breakdown stays raw


def test_sightseeing_preset_does_not_change_cost_of_dropping_a_meal() -> None:
    inp = load_scenario_a()
    sightseeing = next(s for s in STRATEGIES if s.name == "sightseeing").weights
    changes = plan(inp, base=original_plan(inp), cafe=None)  # cafe category
    assert compute_cost(inp, changes, sightseeing).rc_total == pytest.approx(
        compute_cost(inp, changes, DEFAULT_WEIGHTS).rc_total
    )


def test_identical_candidates_are_returned_once() -> None:
    results = recover(load_scenario_a())
    plans = [r.changes for r in results]
    assert len(plans) == len(set(plans))
    assert results[0].strategy == "balanced"
