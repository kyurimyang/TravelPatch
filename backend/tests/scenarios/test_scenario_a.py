import json
from pathlib import Path

from app.schemas.enums import Op
from app.schemas.recovery import RecoveryInput


def _load(name: str) -> tuple[RecoveryInput, dict]:
    raw = json.loads((Path(__file__).parent / name).read_text(encoding="utf-8"))
    expected = raw.pop("expected")
    return RecoveryInput.model_validate(raw), expected


def test_scenario_a_input_is_valid() -> None:
    inp, _ = _load("scenario_a.json")
    assert len(inp.activities) == 8


def test_scenario_a_recovery() -> None:
    # Red until the engine exists (step 4-5).
    from app.engine.recover import recover

    inp, expected = _load("scenario_a.json")
    results = recover(inp)
    assert results

    all_ids = {a.id for a in inp.activities}
    for r in results:
        assert r.violations == expected["violations"]
        assert {c.activity_id for c in r.changes} == all_ids  # keep rows included
        dropped = {c.activity_id for c in r.changes if c.op == Op.DROP}
        assert not dropped & set(expected["must_kept"])

    best_dropped = sorted(c.activity_id for c in results[0].changes if c.op == Op.DROP)
    assert best_dropped == expected["dropped"]
