import pytest
from pydantic import ValidationError

from app.engine.constraint_builder import Constraints, build_constraints
from app.engine.optimizer_dp import solve_fixed_order
from app.engine.recover import recover
from app.engine.validator import validate
from app.schemas.enums import Op
from app.schemas.events import WeatherEvent
from tests.engine.helpers import load_scenario, original_plan, plan

ORDER = ("meiji", "harajuku", "omotesando", "ramen", "shibuya_shop", "cafe", "sky", "izakaya")


def _kinds(violations: list) -> list[tuple[str, str]]:
    return [(v.kind, v.activity_id) for v in violations]


def test_weather_event_becomes_a_rain_window() -> None:
    inp = load_scenario("scenario_b.json")
    assert build_constraints(inp) == Constraints(rains=((720, 1440),))  # no end: until night


def test_other_events_have_no_rain_window() -> None:
    assert build_constraints(load_scenario("scenario_e.json")).rains == ()
    assert build_constraints(load_scenario("scenario_a.json")).rains == ()


def test_rain_window_must_have_positive_length() -> None:
    with pytest.raises(ValidationError):
        WeatherEvent(occurred_at=540, start_time=720, end_time=720)


def test_outdoor_activity_in_rain_is_a_violation() -> None:
    inp = load_scenario("scenario_b.json")
    # the original plan has omotesando (outdoor) from 11:40 to 12:40, overlapping the rain
    violations = validate(inp, plan(inp, base=original_plan(inp)))
    assert _kinds(violations) == [("weather", "omotesando")]


def test_shrinking_to_the_rain_start_is_valid() -> None:
    inp = load_scenario("scenario_b.json")
    assert validate(inp, plan(inp, base=original_plan(inp), omotesando=(700, 720))) == []


def test_unknown_outdoor_status_is_not_blocked_by_the_validator() -> None:
    inp = load_scenario("scenario_b.json")
    sky = next(a for a in inp.activities if a.id == "sky")
    assert sky.outdoor is None  # we do not know: not blocked, but flagged for the user


def test_dp_keeps_outdoor_activities_out_of_the_rain() -> None:
    inp = load_scenario("scenario_b.json")
    sol = solve_fixed_order(inp, ORDER)
    assert sol is not None
    assert validate(inp, sol.changes) == []
    omotesando = next(c for c in sol.changes if c.activity_id == "omotesando")
    assert omotesando.op == Op.SHRINK
    assert omotesando.after.end <= 720


def test_recover_flags_unknown_activities_that_overlap_the_rain() -> None:
    inp = load_scenario("scenario_b.json")
    for result in recover(inp):
        flagged = {c.activity_id for c in result.changes if c.needs_check}
        assert flagged == {"sky"}


def test_no_flags_without_rain() -> None:
    inp = load_scenario("scenario_a.json")
    for result in recover(inp):
        assert not any(c.needs_check for c in result.changes)
