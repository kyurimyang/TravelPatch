import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from eval.llm_plan import (
    LLMPlan,
    PlanFormatError,
    PlanItem,
    build_prompt,
    hhmm,
    parse_hhmm,
    plan_to_changes,
    repair_prompt,
)

from app.engine.validator import Violation
from app.schemas.enums import Op
from app.schemas.recovery import RecoveryInput

SCENARIOS = ROOT / "backend" / "tests" / "scenarios"


def _load(path: Path) -> RecoveryInput:
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop("expected", None)
    return RecoveryInput.model_validate(raw)


@pytest.fixture(scope="module")
def scenario_a() -> RecoveryInput:
    return _load(SCENARIOS / "scenario_a.json")


def test_hhmm_round_trip_and_bounds():
    assert hhmm(570) == "09:30"
    assert parse_hhmm("09:30") == 570 and parse_hhmm("9:05") == 545 and parse_hhmm("24:00") == 1440
    for bad in ["25:00", "12:60", "noon", "12시", ""]:
        with pytest.raises(PlanFormatError):
            parse_hhmm(bad)


def test_prompt_builds_for_every_eval50_scenario():
    paths = sorted((SCENARIOS / "eval50").glob("*.json"))
    assert len(paths) == 50
    for path in paths:
        inp = _load(path)
        prompt = build_prompt(inp)
        assert hhmm(inp.now) in prompt
        assert all(a.id in prompt for a in inp.activities)


def test_prompt_states_the_event_in_words(scenario_a):
    assert "can only start moving at" in build_prompt(scenario_a)


def test_missing_items_are_kept(scenario_a):
    changes = plan_to_changes(scenario_a, LLMPlan(items=[]))
    assert len(changes) == len(scenario_a.activities)
    assert all(c.op == Op.KEEP and c.before == c.after for c in changes)


def test_ops_follow_the_new_slot(scenario_a):
    first = min(scenario_a.activities, key=lambda a: (a.planned_start, a.id))
    s, e = first.planned_start, first.planned_end

    def op_of(start, end):
        item = PlanItem(activity_id=first.id, action="change", start=start, end=end)
        return plan_to_changes(scenario_a, LLMPlan(items=[item]))[0].op

    assert op_of(hhmm(s + 10), hhmm(e + 10)) == Op.MOVE
    assert op_of(hhmm(s), hhmm(e - 5)) == Op.SHRINK
    assert op_of(hhmm(s), hhmm(e + 5)) == Op.EXTEND
    assert op_of(hhmm(s), hhmm(e)) == Op.KEEP


def test_drop_has_no_after(scenario_a):
    item = PlanItem(activity_id=scenario_a.activities[0].id, action="drop", start=None, end=None)
    change = next(
        c
        for c in plan_to_changes(scenario_a, LLMPlan(items=[item]))
        if c.activity_id == item.activity_id
    )
    assert change.op == Op.DROP and change.after is None


@pytest.mark.parametrize(
    ("start", "end"), [(None, "10:00"), ("10:00", None), ("11:00", "10:00"), ("x", "10:00")]
)
def test_bad_change_is_a_format_error(scenario_a, start, end):
    item = PlanItem(activity_id=scenario_a.activities[0].id, action="change", start=start, end=end)
    with pytest.raises(PlanFormatError):
        plan_to_changes(scenario_a, LLMPlan(items=[item]))


def test_repair_prompt_lists_problems(scenario_a):
    problems = [Violation(kind="travel", activity_id="ramen", detail="too tight")]
    text = repair_prompt(scenario_a, LLMPlan(items=[]), problems)
    assert "- travel: too tight" in text and "previous plan" in text


@pytest.fixture(scope="module")
def closure_input() -> RecoveryInput:
    return _load(SCENARIOS / "eval50" / "i00_closure.json")


def test_replacement_places_are_offered_only_when_the_input_has_them(closure_input, scenario_a):
    offered = build_prompt(closure_input)
    assert "Replacement places" in offered and "a0_alt1 | a0 |" in offered
    assert "replace it with one of the replacement places" in offered
    assert "Replacement places" not in build_prompt(scenario_a)


def test_substitute_action_becomes_a_substitute_change(closure_input):
    item = PlanItem(
        activity_id="a0", action="substitute", start="10:00", end="10:30", substitute_id="a0_alt2"
    )
    change = next(
        c for c in plan_to_changes(closure_input, LLMPlan(items=[item])) if c.activity_id == "a0"
    )
    assert change.op == Op.SUBSTITUTE and change.substitute_id == "a0_alt2"


def test_substitute_without_id_is_a_format_error(closure_input):
    item = PlanItem(activity_id="a0", action="substitute", start="10:00", end="10:30")
    with pytest.raises(PlanFormatError):
        plan_to_changes(closure_input, LLMPlan(items=[item]))
