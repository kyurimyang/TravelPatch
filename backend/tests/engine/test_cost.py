import pytest

from app.engine.cost import compute_cost
from tests.engine.helpers import SOLUTION_A, load_scenario_a, original_plan, plan


def test_documented_solution_matches_doc_preservation() -> None:
    inp = load_scenario_a()
    cost = compute_cost(inp, plan(inp))
    # Planning doc says "about 89%": 1 - (1 + 5*10/60 + 3*15/60 + 1*10/45) / 26
    assert cost.preservation_rate == pytest.approx(0.892, abs=0.001)
    b = cost.breakdown
    assert b.d_drop == 1.0
    assert b.d_shrink == pytest.approx(1.806, abs=0.001)  # 5*10/60 + 3*15/60 + 1*10/45
    assert b.d_order == 0.0
    assert b.d_intent == 0.0  # "street" survives through harajuku


def test_unchanged_plan_costs_nothing() -> None:
    inp = load_scenario_a()
    cost = compute_cost(inp, plan(inp, base=original_plan(inp)))
    assert cost.rc_total == 0.0
    assert cost.preservation_rate == 1.0


def test_dropping_optional_costs_its_value() -> None:
    inp = load_scenario_a()
    cost = compute_cost(inp, plan(inp, base=original_plan(inp), cafe=None))
    assert cost.breakdown.d_drop == 1.0
    assert cost.preservation_rate == pytest.approx(1 - 1 / 26)
    assert cost.breakdown.d_intent == 1.0  # "cafe" tag disappears


def test_swapping_two_activities_is_one_inversion() -> None:
    inp = load_scenario_a()
    swapped = plan(inp, base=original_plan(inp), omotesando=(770, 830), ramen=(700, 760))
    assert compute_cost(inp, swapped).breakdown.d_order == 1.0


def test_solution_is_deterministic() -> None:
    inp = load_scenario_a()
    assert compute_cost(inp, plan(inp)) == compute_cost(inp, tuple(reversed(plan(inp))))


def test_solution_table_covers_all_activities() -> None:
    assert set(SOLUTION_A) == {a.id for a in load_scenario_a().activities}
