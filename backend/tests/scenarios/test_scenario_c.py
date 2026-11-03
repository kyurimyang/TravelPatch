import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.enums import Op
from app.schemas.recovery import RecoveryChange, RecoveryInput, Slot


def _load() -> tuple[RecoveryInput, dict]:
    raw = json.loads((Path(__file__).parent / "scenario_c.json").read_text(encoding="utf-8"))
    expected = raw.pop("expected")
    return RecoveryInput.model_validate(raw), expected


def test_scenario_c_input_is_valid() -> None:
    inp, _ = _load()
    assert len(inp.activities) == 8
    assert len(inp.substitutes) == 2


def test_substitute_op_needs_substitute_id_and_only_it() -> None:
    slot = Slot(start=1170, end=1260)
    with pytest.raises(ValidationError):
        RecoveryChange(activity_id="izakaya", op=Op.SUBSTITUTE, before=slot, after=slot)
    with pytest.raises(ValidationError):
        RecoveryChange(activity_id="izakaya", op=Op.KEEP, before=slot, after=slot, substitute_id="x")


def test_substitute_must_replace_a_known_activity() -> None:
    inp, _ = _load()
    bad = inp.substitutes[0].model_copy(update={"replaces": "nowhere"})
    with pytest.raises(ValidationError):
        RecoveryInput.model_validate({**inp.model_dump(), "substitutes": [bad.model_dump()]})


def test_travel_table_must_cover_substitutes() -> None:
    inp, _ = _load()
    short = [t.model_dump() for t in inp.travel if "izakaya_far" not in (t.a, t.b)]
    with pytest.raises(ValidationError):
        RecoveryInput.model_validate({**inp.model_dump(), "travel": short})


def test_scenario_c_recovery() -> None:
    from app.engine.recover import recover

    inp, expected = _load()
    results = recover(inp)
    assert results
    for r in results:
        by_id = {c.activity_id: c for c in r.changes}
        assert r.violations == expected["violations"]
        assert {c.activity_id for c in r.changes} == {a.id for a in inp.activities}
        for act_id in expected["substituted"]:
            assert by_id[act_id].op == Op.SUBSTITUTE  # the closed must-activity is replaced
            assert by_id[act_id].substitute_id in {s.id for s in inp.substitutes}
        if r.strategy == "balanced":  # the default plan; "relaxed" needs 20 min buffers and must move others
            for act_id in expected["unchanged"]:
                assert by_id[act_id].op == Op.KEEP  # nothing else moves
