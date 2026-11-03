import pytest

from app.engine.cost import compute_cost
from tests.engine.helpers import load_scenario_c, plan_c

# Scenario C values: izakaya is must (5), substitutability 0.6; all tiers sum to 26.
TOTAL_VALUE = 26


def test_substitute_costs_value_times_one_minus_substitutability_plus_penalty() -> None:
    inp = load_scenario_c()
    near = compute_cost(inp, plan_c(inp, (1170, 1260), "izakaya_near"))
    far = compute_cost(inp, plan_c(inp, (1170, 1260), "izakaya_far"))
    assert near.breakdown.d_sub == pytest.approx(5 * 0.4 + 0.3)
    assert far.breakdown.d_sub == pytest.approx(5 * 0.4 + 0.6)
    assert near.preservation_rate == pytest.approx(1 - 2.3 / TOTAL_VALUE)


def test_move_cost_follows_the_substitutes_own_travel_time() -> None:
    inp = load_scenario_c()
    near = compute_cost(inp, plan_c(inp, (1170, 1260), "izakaya_near"))
    far = compute_cost(inp, plan_c(inp, (1170, 1260), "izakaya_far"))
    assert near.breakdown.d_move == pytest.approx(0)
    assert far.breakdown.d_move == pytest.approx(10 / 60)  # sky -> far is 10 min longer


def test_shorter_stay_at_the_new_place_is_not_also_counted_as_shrink() -> None:
    inp = load_scenario_c()
    short = compute_cost(inp, plan_c(inp, (1170, 1230), "izakaya_near"))
    assert short.breakdown.d_shrink == 0
    assert short.breakdown.d_sub == pytest.approx(2.3)
