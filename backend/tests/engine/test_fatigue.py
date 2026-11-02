import pytest
from pydantic import ValidationError

from app.engine.constraint_builder import build_constraints
from app.engine.optimizer_dp import solve_fixed_order
from app.engine.recover import recover
from app.engine.validator import validate
from app.schemas.enums import Op
from app.schemas.events import FatigueEvent
from tests.engine.helpers import load_scenario, original_plan, plan

ORDER = ("ramen", "shibuya_shop", "cafe", "sky", "izakaya")


def _kinds(violations: list) -> list[tuple[str, str]]:
    return [(v.kind, v.activity_id) for v in violations]


def test_walking_ratio_defaults_to_half_and_must_be_a_share() -> None:
    assert FatigueEvent(occurred_at=820).walking_ratio == 0.5
    for bad in (0, 1.5):
        with pytest.raises(ValidationError):
            FatigueEvent(occurred_at=820, walking_ratio=bad)


def test_only_walking_activities_get_a_cap() -> None:
    inp = load_scenario("scenario_d.json")
    # shop: 90 min planned -> 45; ramen is in progress, sky and izakaya are reserved/not walking
    assert build_constraints(inp).duration_caps == (("shibuya_shop", 45),)


def test_cap_never_goes_below_the_minimum_stay() -> None:
    inp = load_scenario("scenario_d.json")
    strict = inp.model_copy(update={"event": inp.event.model_copy(update={"walking_ratio": 0.1})})
    assert build_constraints(strict).duration_cap("shibuya_shop") == 30  # min_duration


def test_walking_activity_longer_than_the_cap_is_a_violation() -> None:
    inp = load_scenario("scenario_d.json")
    assert _kinds(validate(inp, plan(inp, base=original_plan(inp)))) == [
        ("fatigue", "shibuya_shop")
    ]


def test_shrinking_to_the_cap_is_valid() -> None:
    inp = load_scenario("scenario_d.json")
    assert validate(inp, plan(inp, base=original_plan(inp), shibuya_shop=(850, 895))) == []


def test_dp_shrinks_only_the_walking_activity() -> None:
    inp = load_scenario("scenario_d.json")
    sol = solve_fixed_order(inp, ORDER)
    assert sol is not None
    assert validate(inp, sol.changes) == []
    shrunk = [c.activity_id for c in sol.changes if c.op == Op.SHRINK]
    assert shrunk == ["shibuya_shop"]


def test_unknown_walking_load_is_flagged_not_guessed() -> None:
    inp = load_scenario("scenario_d.json")
    unknown = inp.model_copy(
        update={
            "activities": tuple(
                a.model_copy(update={"walking": None}) if a.id == "cafe" else a
                for a in inp.activities
            )
        }
    )
    for result in recover(unknown):
        assert {c.activity_id for c in result.changes if c.needs_check} == {"cafe"}
