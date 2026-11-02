import json
from pathlib import Path

from app.engine.recover import recover
from app.schemas.enums import Op
from app.schemas.recovery import RecoveryInput


def test_scenario_b_recovery() -> None:
    raw = json.loads((Path(__file__).parent / "scenario_b.json").read_text(encoding="utf-8"))
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
        flagged = sorted(c.activity_id for c in r.changes if c.needs_check)
        assert flagged == expected["needs_check"]

    # The default candidate only shrinks omotesando; nothing is dropped.
    default = results[0]
    assert [c.activity_id for c in default.changes if c.op == Op.SHRINK] == expected["shrunk"]
    assert not [c for c in default.changes if c.op == Op.DROP]
    # Planning doc: the rain only touches omotesando, everything else stays as planned.
    assert [c.activity_id for c in default.changes if c.op != Op.KEEP] == expected["changed"]
