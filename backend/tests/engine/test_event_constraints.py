from app.engine.cost import compute_cost
from app.engine.optimizer_dp import solve_fixed_order
from app.engine.presets import STRATEGIES
from app.engine.validator import validate
from app.schemas.enums import Op
from tests.engine.helpers import SOLUTION_E, load_scenario, load_scenario_a, plan

ORDER_A = ("meiji", "harajuku", "omotesando", "ramen", "shibuya_shop", "cafe", "sky", "izakaya")
ORDER_E = ("harajuku", "omotesando", "ramen", "shibuya_shop", "cafe", "sky", "izakaya")


def _kinds(violations: list) -> list[tuple[str, str]]:
    return [(v.kind, v.activity_id) for v in violations]


def test_buffer_is_added_on_top_of_travel() -> None:
    inp = load_scenario_a()
    # harajuku starts exactly on time (travel 5); with a 10 min buffer it is too early
    assert validate(inp, plan(inp)) == []
    assert ("travel", "harajuku") in _kinds(validate(inp, plan(inp), min_buffer=10))


def test_relaxed_strategy_plan_respects_its_buffer() -> None:
    inp = load_scenario_a()
    relaxed = next(s for s in STRATEGIES if s.name == "relaxed")
    sol = solve_fixed_order(inp, ORDER_A, relaxed.weights, relaxed.min_buffer)
    assert sol is not None
    assert validate(inp, sol.changes, relaxed.min_buffer) == []


def test_documented_plan_for_scenario_e_is_valid() -> None:
    inp = load_scenario("scenario_e.json")
    assert validate(inp, plan(inp, base=SOLUTION_E)) == []


def test_extension_is_a_hard_requirement() -> None:
    inp = load_scenario("scenario_e.json")
    not_extended = plan(inp, base=SOLUTION_E, harajuku=(630, 690))
    assert _kinds(validate(inp, not_extended)) == [("event", "harajuku")]


def test_activity_in_progress_cannot_move_its_start() -> None:
    inp = load_scenario("scenario_e.json")
    moved = plan(inp, base=SOLUTION_E, harajuku=(640, 730))
    assert ("in_progress", "harajuku") in _kinds(validate(inp, moved))


def test_first_activity_ahead_must_be_reachable_from_where_the_user_is() -> None:
    inp = load_scenario("scenario_e.json")
    # now 690 at harajuku, omotesando is 10 min away: 695 is too early
    too_early = plan(inp, base=SOLUTION_E, omotesando=(695, 725))
    assert ("origin", "omotesando") in _kinds(validate(inp, too_early))


def test_dp_extends_the_activity_and_is_no_worse_than_the_documented_plan() -> None:
    inp = load_scenario("scenario_e.json")
    sol = solve_fixed_order(inp, ORDER_E)
    assert sol is not None
    assert validate(inp, sol.changes) == []
    harajuku = next(c for c in sol.changes if c.activity_id == "harajuku")
    assert harajuku.op == Op.EXTEND
    assert harajuku.after.end - harajuku.after.start == 90
    documented = compute_cost(inp, plan(inp, base=SOLUTION_E)).rc_total
    assert compute_cost(inp, sol.changes).rc_total <= documented + 1e-9
