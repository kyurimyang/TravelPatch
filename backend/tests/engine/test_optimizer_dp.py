from app.engine.cost import compute_cost
from app.engine.optimizer_dp import solve_fixed_order
from app.engine.recover import recover
from app.engine.validator import validate
from app.schemas.enums import Op
from tests.engine.helpers import SOLUTION_A, load_scenario_a, plan

ORDER = ("meiji", "harajuku", "omotesando", "ramen", "shibuya_shop", "cafe", "sky", "izakaya")


def test_solution_has_no_violations_and_keeps_must() -> None:
    inp = load_scenario_a()
    sol = solve_fixed_order(inp, ORDER)
    assert sol is not None
    assert validate(inp, sol.changes) == []
    dropped = {c.activity_id for c in sol.changes if c.op == Op.DROP}
    assert not dropped & {"meiji", "ramen", "sky", "izakaya"}


HAND_MADE = {
    "doc table": SOLUTION_A,
    "keep all": {
        "meiji": (680, 740), "harajuku": (745, 805), "omotesando": (815, 835), "ramen": (845, 905),
        "shibuya_shop": (925, 955), "cafe": (960, 990), "sky": (1020, 1080), "izakaya": (1170, 1260),
    },
    "drop omotesando, shrink shop and cafe": {
        "meiji": (680, 740), "harajuku": (745, 805), "omotesando": None, "ramen": (820, 880),
        "shibuya_shop": (900, 975), "cafe": (980, 1010), "sky": (1020, 1080), "izakaya": (1170, 1260),
    },
}


def test_solution_is_at_least_as_good_as_hand_made_candidates() -> None:
    inp = load_scenario_a()
    sol = solve_fixed_order(inp, ORDER)
    assert sol is not None
    best = compute_cost(inp, sol.changes).rc_total
    for name, candidate in HAND_MADE.items():
        changes = plan(inp, base=candidate)
        assert validate(inp, changes) == [], name
        assert best <= compute_cost(inp, changes).rc_total + 1e-9, name


def test_same_input_gives_identical_output() -> None:
    inp = load_scenario_a()
    assert solve_fixed_order(inp, ORDER) == solve_fixed_order(inp, ORDER)


def test_returns_none_when_a_reserved_must_cannot_fit() -> None:
    inp = load_scenario_a()
    late = inp.model_copy(
        update={"event": inp.event.model_copy(update={"occurred_at": 1200, "start_time": 1200})}
    )
    assert solve_fixed_order(late, ORDER) is None
    assert recover(late) == []


def test_recover_returns_validated_candidates_balanced_first() -> None:
    results = recover(load_scenario_a())
    assert results[0].strategy == "balanced"
    for r in results:
        assert r.violations == 0
        assert 0.0 <= r.preservation_rate <= 1.0
