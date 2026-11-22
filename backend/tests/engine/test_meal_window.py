"""A3 (review 2026-11-19): a meal may not drift far from when it was planned.

Rule (hard constraint): a placed meal starts within MEAL_WINDOW_MINUTES of its planned start,
both ways, bounds included. A substituted meal keeps the window of the activity it replaces.
A meal that cannot fit is dropped (or, if must, there is no plan) instead of lunch at 17:00.

Scenario A meals: ramen 12:50-13:50 (planned_start 770), izakaya 19:30 (reserved).
"""

import pytest

from app.engine.presets import MEAL_WINDOW_MINUTES
from app.engine.recover import recover
from app.engine.validator import validate
from tests.engine.helpers import (
    load_scenario,
    load_scenario_a,
    load_scenario_c,
    original_plan,
    plan,
    plan_c,
)

RAMEN_START = 770


def _kinds(violations: list) -> set[tuple[str, str]]:
    return {(v.kind, v.activity_id) for v in violations}


def test_window_is_90_minutes() -> None:
    assert MEAL_WINDOW_MINUTES == 90


def test_meal_too_late_is_a_violation() -> None:
    inp = load_scenario_a()
    late = RAMEN_START + MEAL_WINDOW_MINUTES + 5
    assert ("meal_window", "ramen") in _kinds(validate(inp, plan(inp, ramen=(late, late + 60))))


def test_meal_too_early_is_a_violation() -> None:
    inp = load_scenario_a()
    early = RAMEN_START - MEAL_WINDOW_MINUTES - 5
    assert ("meal_window", "ramen") in _kinds(validate(inp, plan(inp, ramen=(early, early + 60))))


@pytest.mark.parametrize("shift", [-MEAL_WINDOW_MINUTES, MEAL_WINDOW_MINUTES])
def test_window_bounds_are_allowed(shift: int) -> None:
    inp = load_scenario_a()
    start = RAMEN_START + shift
    kinds = _kinds(validate(inp, plan(inp, ramen=(start, start + 60))))
    assert ("meal_window", "ramen") not in kinds


def test_dropped_meal_is_not_a_window_violation() -> None:
    inp = load_scenario_a()
    assert ("meal_window", "ramen") not in _kinds(validate(inp, plan(inp, ramen=None)))


def test_non_meal_may_move_further() -> None:
    inp = load_scenario_a()
    # The cafe (not a meal) 2 hours late may break other rules, but never the meal window.
    kinds = _kinds(validate(inp, plan(inp, cafe=(950 + 120, 950 + 165))))
    assert not any(kind == "meal_window" for kind, _ in kinds)


def test_substitute_meal_keeps_the_window_of_what_it_replaces() -> None:
    inp = load_scenario_c()  # izakaya (planned 19:30) is closed
    late = 1170 + MEAL_WINDOW_MINUTES + 5
    changes = plan_c(inp, (late, late + 50), sub="izakaya_near")
    assert ("meal_window", "izakaya") in _kinds(validate(inp, changes))


# Measured before the change (2026-11-19): these candidates moved a meal 95-145 minutes.
@pytest.mark.parametrize("name", ["i00_delay.json", "i06_weather.json", "i07_delay.json"])
def test_engine_keeps_meals_in_their_window(name: str) -> None:
    inp = load_scenario(f"eval50/{name}")
    meals = {a.id: a.planned_start for a in inp.activities if a.category == "meal"}
    for result in recover(inp):
        for c in result.changes:
            if c.activity_id in meals and c.after is not None:
                shift = c.after.start - meals[c.activity_id]
                assert abs(shift) <= MEAL_WINDOW_MINUTES, (result.strategy, c.activity_id, shift)


def test_a_booked_meal_follows_its_booking_not_the_window() -> None:
    # The user moved the dinner booking 2 hours: the booking wins over the window. The window
    # stops the engine from dragging meals around; it does not overrule what the user booked.
    inp = load_scenario("scenario_f.json")
    later = 1170 + 120
    ev = inp.event.model_copy(update={"new_time": later})
    moved = inp.model_copy(update={"event": ev})
    changes = plan(moved, original_plan(moved), izakaya=(later, later + 90))
    assert ("meal_window", "izakaya") not in _kinds(validate(moved, changes))


def test_a_substitute_for_a_booked_meal_has_the_window_again() -> None:
    # A replacement place has no booking, so the window applies (test above for the booking).
    inp = load_scenario_c()
    late = 1170 + MEAL_WINDOW_MINUTES + 5
    assert ("meal_window", "izakaya") in _kinds(
        validate(inp, plan_c(inp, (late, late + 50), sub="izakaya_near"))
    )


def test_a_must_meal_out_of_reach_has_no_plan_and_says_why() -> None:
    # Overslept until 15:00: lunch (must, 12:50) may start at 14:20 at the latest.
    from app.engine.conflict_detector import find_blockers

    inp = load_scenario_a()
    late = inp.model_copy(update={"event": inp.event.model_copy(update={"start_time": 900})})
    assert recover(late) == []
    blockers = [(b.kind, b.activity_id, b.blocking_time) for b in find_blockers(late)]
    assert ("meal_out_of_reach", "ramen", RAMEN_START + MEAL_WINDOW_MINUTES) in blockers
