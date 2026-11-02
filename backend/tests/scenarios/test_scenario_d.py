import json
from pathlib import Path

from app.engine.recover import recover
from app.schemas.enums import Op
from app.schemas.recovery import RecoveryInput


def test_scenario_d_recovery() -> None:
    raw = json.loads((Path(__file__).parent / "scenario_d.json").read_text(encoding="utf-8"))
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
        for activity_id, limit in expected["max_minutes"].items():
            after = next(c.after for c in r.changes if c.activity_id == activity_id)
            if after is not None:
                assert after.end - after.start <= limit

    default = results[0]
    assert [c.activity_id for c in default.changes if c.op == Op.SHRINK] == expected["shrunk"]
    assert not [c for c in default.changes if c.op == Op.DROP]
