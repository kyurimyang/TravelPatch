import json
from pathlib import Path

from app.engine.validator import validate
from app.schemas.enums import Op
from app.schemas.recovery import RecoveryChange, RecoveryInput, Slot


def _keep_everything(name: str) -> tuple[RecoveryInput, tuple[RecoveryChange, ...]]:
    raw = json.loads((Path(__file__).parents[1] / "scenarios" / name).read_text(encoding="utf-8"))
    raw.pop("expected")
    inp = RecoveryInput.model_validate(raw)
    keep = tuple(
        RecoveryChange(
            activity_id=a.id,
            op=Op.KEEP,
            before=Slot(start=a.planned_start, end=a.planned_end),
            after=Slot(start=a.planned_start, end=a.planned_end),
        )
        for a in inp.activities
    )
    return inp, keep


def test_unchanged_activity_in_the_past_is_a_violation() -> None:
    # The delayed user can only move from 10:25 (625): a0 at 9:55 cannot be attended.
    inp, keep = _keep_everything("eval50/i02_delay.json")
    past = [v for v in validate(inp, keep) if v.kind == "past"]
    assert [v.activity_id for v in past] == ["a0"]


def test_the_activity_the_user_is_in_may_stay_in_the_past() -> None:
    # Extending the activity you are inside: its start is before now and that is fine.
    inp, keep = _keep_everything("scenario_e.json")
    harajuku = next(a for a in inp.activities if a.id == "harajuku")
    assert inp.event.location_id == "harajuku" and harajuku.planned_start < inp.now
    assert not [v for v in validate(inp, keep) if v.kind == "past"]
