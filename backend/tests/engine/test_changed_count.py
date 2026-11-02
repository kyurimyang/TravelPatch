import pytest

from app.engine.cost import compute_cost
from app.engine.presets import Strategy, Weights
from app.engine.recover import recover
from app.schemas.enums import Op
from tests.engine.helpers import load_scenario, load_scenario_a, original_plan, plan


def _changed(inp, w_changed: float) -> int:
    result = recover(inp, (Strategy(name="x", weights=Weights(w_changed=w_changed)),))[0]
    return sum(1 for c in result.changes if c.op != Op.KEEP)


def test_unchanged_plan_has_no_changed_activities() -> None:
    inp = load_scenario_a()
    assert compute_cost(inp, plan(inp, base=original_plan(inp))).breakdown.d_changed == 0.0


def test_documented_solution_changes_six_activities() -> None:
    inp = load_scenario_a()
    # meiji, harajuku, omotesando (dropped), ramen, shop, cafe move; sky and izakaya stay
    assert compute_cost(inp, plan(inp)).breakdown.d_changed == 6.0


def test_weight_scales_the_total_cost_linearly() -> None:
    inp = load_scenario_a()
    off = compute_cost(inp, plan(inp), Weights(w_changed=0.0)).rc_total
    on = compute_cost(inp, plan(inp), Weights(w_changed=0.5)).rc_total
    assert on - off == pytest.approx(0.5 * 6)


def test_a_higher_weight_never_increases_the_number_of_changes() -> None:
    for name in ("scenario_a.json", "scenario_b.json", "scenario_d.json", "scenario_e.json"):
        inp = load_scenario(name)
        counts = [_changed(inp, w) for w in (0.0, 0.1, 0.3, 1.0)]
        assert counts == sorted(counts, reverse=True), (name, counts)
