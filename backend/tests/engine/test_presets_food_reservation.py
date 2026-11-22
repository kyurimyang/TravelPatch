"""Limit 5 (2026-11-22): the two presets from CLAUDE.md 6 that were missing.

- food (음식 보존): dropping a meal is a hard "no" (not a weight).
- reservation (예약 보존): arrive RESERVATION_BUFFER minutes before every booking.

Both are hard rules of their strategy, so the DP and the validator each enforce them. All six
strategies are solved; at most three distinct candidates are shown (balanced first).
"""

import pytest

from app.engine.presets import STRATEGIES
from app.engine.recover import recover
from app.engine.validator import validate
from app.schemas.enums import Category
from tests.engine.helpers import load_scenario, load_scenario_a, original_plan, plan

BY_NAME = {s.name: s for s in STRATEGIES}
# eval50 scenarios where the balanced candidate drops a meal (measured 2026-11-22).
DROPS_A_MEAL = ["i00_delay", "i04_weather", "i06_weather", "i07_delay", "i08_weather"]


def _kinds(violations: list) -> set[tuple[str, str]]:
    return {(v.kind, v.activity_id) for v in violations}


def test_six_strategies_balanced_first() -> None:
    assert [s.name for s in STRATEGIES] == [
        "balanced",
        "sightseeing",
        "low_travel",
        "relaxed",
        "food",
        "reservation",
    ]
    assert BY_NAME["food"].no_drop_categories == (Category.MEAL,)
    assert BY_NAME["reservation"].reservation_buffer == 15


def test_validator_refuses_a_dropped_meal_under_food() -> None:
    inp = load_scenario_a()
    changes = plan(inp, original_plan(inp), ramen=None)
    assert ("no_drop", "ramen") in _kinds(validate(inp, changes, no_drop_categories=(Category.MEAL,)))
    assert ("no_drop", "ramen") not in _kinds(validate(inp, changes))


def test_validator_wants_the_buffer_before_a_booking() -> None:
    inp = load_scenario_a()
    # The sky deck is booked 17:00; the cafe ends 16:35 and the walk is short: no 15 min spare
    # once the cafe runs to 16:50.
    changes = plan(inp, original_plan(inp), cafe=(950, 1010))
    with_buffer = _kinds(validate(inp, changes, reservation_buffer=15))
    assert ("reservation_buffer", "sky") in with_buffer
    assert ("reservation_buffer", "sky") not in _kinds(validate(inp, changes))


@pytest.mark.parametrize("name", DROPS_A_MEAL)
def test_food_keeps_every_meal_or_offers_nothing(name: str) -> None:
    inp = load_scenario(f"eval50/{name}.json")
    meals = {a.id for a in inp.activities if a.category == Category.MEAL}
    (only,) = recover(inp, strategies=(BY_NAME["food"],), max_tries=0) or (None,)
    if only is None:
        return  # no plan keeps every meal: allowed, it is then simply not offered
    assert only.violations == 0
    assert all(c.after is not None for c in only.changes if c.activity_id in meals)


def test_reservation_candidates_leave_the_buffer() -> None:
    inp = load_scenario_a()
    (only,) = recover(inp, strategies=(BY_NAME["reservation"],), max_tries=0)
    assert validate(inp, only.changes, reservation_buffer=15) == []


# i01_extend and i07_delay give 4 distinct candidates from the six strategies (2026-11-22).
@pytest.mark.parametrize(
    "name",
    ["scenario_a.json", "eval50/i00_delay.json", "eval50/i01_extend.json", "eval50/i07_delay.json"],
)
def test_at_most_three_distinct_candidates_balanced_first(name: str) -> None:
    results = recover(load_scenario(name))
    assert 1 <= len(results) <= 3
    assert results[0].strategy == "balanced"
    assert len({r.changes for r in results}) == len(results)


def test_shown_candidates_are_deterministic() -> None:
    inp = load_scenario("eval50/i00_delay.json")
    assert recover(inp) == recover(inp)


def test_the_extra_one_left_out_is_the_most_alike() -> None:
    # i07_delay: balanced, low_travel, relaxed, food, reservation are all distinct (5 since the
    # relocation search, 2026-11-22; 4 before); those not shown must be the closest to those
    # shown (fewest activities that differ).
    from app.engine.recover import shown_distance

    inp = load_scenario("eval50/i07_delay.json")
    shown = recover(inp)
    everything = recover(inp, limit=None)
    assert len(everything) == 5 and len(shown) == 3
    left_out = [r for r in everything if r not in shown]
    for lo in left_out:
        worst = min(min(shown_distance(lo, s) for s in shown[:k]) for k in (1, 2))
        for r in shown[1:]:
            assert min(shown_distance(r, s) for s in shown[: shown.index(r)]) >= worst


def test_a_rule_with_nothing_to_act_on_is_not_solved_again(monkeypatch) -> None:
    # No booking left -> "reservation" is balanced again; no meal -> "food" is too. Skipping them
    # changes no result (equal plans are merged anyway), it only saves the solve.
    from app.engine import recover as rec

    inp = load_scenario_a()
    no_bookings = inp.model_copy(
        update={
            "activities": tuple(
                a.model_copy(update={"reservation_time": None, "category": Category.SIGHTSEEING})
                if a.category == Category.MEAL or a.reservation_time is not None
                else a
                for a in inp.activities
            )
        }
    )
    solved: list[str] = []
    real = rec.solve_candidate
    monkeypatch.setattr(
        rec, "solve_candidate", lambda i, s, *a, **k: solved.append(s.name) or real(i, s, *a, **k)
    )
    with_skip = rec.recover(no_bookings, max_tries=0)
    assert "food" not in solved and "reservation" not in solved
    monkeypatch.setattr(rec, "_same_as_earlier", lambda *a: False)
    assert rec.recover(no_bookings, max_tries=0) == with_skip
