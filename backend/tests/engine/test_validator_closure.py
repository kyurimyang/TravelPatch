from app.engine.validator import validate
from app.schemas.recovery import RecoveryChange, RecoveryInput
from tests.engine.helpers import load_scenario_c as _scenario_c
from tests.engine.helpers import plan_c as _changes


def _kinds(inp: RecoveryInput, changes: tuple[RecoveryChange, ...]) -> set[str]:
    return {v.kind for v in validate(inp, changes)}


def test_valid_substitution_passes() -> None:
    inp = _scenario_c()
    assert validate(inp, _changes(inp, (1170, 1260), "izakaya_near")) == []


def test_closed_activity_cannot_stay() -> None:
    inp = _scenario_c()
    assert _kinds(inp, _changes(inp, (1170, 1260))) == {"closure"}


def test_closed_must_cannot_be_dropped() -> None:
    inp = _scenario_c()
    assert "must_drop" in _kinds(inp, _changes(inp, None))


def test_substitute_must_belong_to_the_activity_and_exist() -> None:
    inp = _scenario_c()
    assert _kinds(inp, _changes(inp, (1170, 1260), "nowhere")) == {"substitute"}
    other = inp.substitutes[0].model_copy(update={"replaces": "cafe"})
    wrong = inp.model_copy(update={"substitutes": (other, inp.substitutes[1])})
    assert _kinds(wrong, _changes(wrong, (1170, 1260), "izakaya_near")) == {"substitute"}


def test_travel_uses_the_substitutes_own_distance() -> None:
    inp = _scenario_c()
    # sky ends 1080. Both candidates are 5 min away from it except the far one (+10).
    # Looking the table up by the original id (5 min) would wrongly accept 1085.
    assert validate(inp, _changes(inp, (1085, 1175), "izakaya_near")) == []
    assert _kinds(inp, _changes(inp, (1085, 1175), "izakaya_far")) == {"travel"}


def test_substitute_is_checked_against_its_own_hours_and_length() -> None:
    inp = _scenario_c()
    assert "hours" in _kinds(inp, _changes(inp, (1260, 1350 + 40), "izakaya_near"))  # past close 1380
    assert "duration" in _kinds(inp, _changes(inp, (1170, 1200), "izakaya_near"))  # shorter than 90
