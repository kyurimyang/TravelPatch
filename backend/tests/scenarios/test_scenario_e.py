import json
from pathlib import Path

from app.engine.recover import recover
from app.schemas.enums import Op
from app.schemas.recovery import RecoveryInput


def test_scenario_e_recovery() -> None:
    raw = json.loads((Path(__file__).parent / "scenario_e.json").read_text(encoding="utf-8"))
    expected = raw.pop("expected")
    inp = RecoveryInput.model_validate(raw)

    results = recover(inp)
    assert results

    all_ids = {a.id for a in inp.activities}
    for r in results:
        assert r.violations == expected["violations"]
        assert {c.activity_id for c in r.changes} == all_ids
        dropped = {c.activity_id for c in r.changes if c.op == Op.DROP}
        assert not dropped & set(expected["must_kept"])
        for activity_id in expected["extended"]:
            change = next(c for c in r.changes if c.activity_id == activity_id)
            assert change.op == Op.EXTEND

    # Planning doc: only the next activity absorbs the extension, lunch onwards is untouched.
    default = results[0]
    ops = {c.activity_id: c.op for c in default.changes}
    assert [i for i, op in ops.items() if op == Op.SHRINK] == expected["shrunk"]
    assert all(ops[i] == Op.KEEP for i in expected["unchanged"])
