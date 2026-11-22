"""Scenario F: the 19:30 izakaya booking moves to 19:00 (RESERVATION_CHANGE).

Expected: the izakaya starts at the new time, everything else stays as planned, no violation.
Until 2026-11-22 the engine refused this event (501) although the interpreter produced it.
"""

import json
from pathlib import Path

from app.engine.candidate import SUPPORTED_EVENTS
from app.engine.conflict_detector import find_blockers
from app.engine.recover import recover
from app.engine.validator import validate
from app.schemas.enums import EventType, Op
from app.schemas.recovery import RecoveryInput
from tests.engine.helpers import original_plan, plan


def _load() -> tuple[RecoveryInput, dict]:
    raw = json.loads((Path(__file__).parent / "scenario_f.json").read_text(encoding="utf-8"))
    expected = raw.pop("expected")
    return RecoveryInput.model_validate(raw), expected


def _kinds(violations: list) -> set[tuple[str, str]]:
    return {(v.kind, v.activity_id) for v in violations}


def test_reservation_change_is_supported() -> None:
    assert EventType.RESERVATION_CHANGE in SUPPORTED_EVENTS


def test_validator_holds_the_new_time_read_from_the_event() -> None:
    inp, _ = _load()
    as_planned = plan(inp, original_plan(inp))  # izakaya still at the old 19:30
    assert ("reservation", "izakaya") in _kinds(validate(inp, as_planned))
    moved = plan(inp, original_plan(inp), izakaya=(1140, 1230))
    assert ("reservation", "izakaya") not in _kinds(validate(inp, moved))


def test_every_candidate_holds_the_new_booking() -> None:
    inp, expected = _load()
    results = recover(inp)
    assert results
    for r in results:
        assert r.violations == 0
        by_id = {c.activity_id: c for c in r.changes}
        assert by_id["izakaya"].after is not None
        assert by_id["izakaya"].after.start == expected["izakaya_start"]
        for act_id in expected["must_kept"]:
            assert by_id[act_id].after is not None


def test_the_representative_candidate_moves_only_the_booking() -> None:
    # Like scenario C's "the rest unchanged", for the first (balanced) candidate: "relaxed"
    # widens every gap to 20 minutes and so reshapes the day whatever the event.
    inp, expected = _load()
    first = recover(inp)[0]
    assert first.strategy == "balanced"
    by_id = {c.activity_id: c for c in first.changes}
    for act_id in expected["unchanged"]:
        assert by_id[act_id].op == Op.KEEP, act_id


def test_the_move_is_explained_by_the_booking() -> None:
    inp, _ = _load()
    izakaya = next(c for c in recover(inp)[0].changes if c.activity_id == "izakaya")
    assert izakaya.reason_data is not None
    assert "reservation" in izakaya.reason_data.forced_by


def test_impossible_new_time_has_no_plan_and_says_why() -> None:
    inp, _ = _load()
    # 18:00: the sky deck (booked 17:00-18:00, must) ends then, and the walk takes 5 minutes.
    ev = inp.event.model_copy(update={"new_time": 1080})
    clash = inp.model_copy(update={"event": ev})
    assert recover(clash) == []
    assert find_blockers(clash)


def test_deterministic() -> None:
    inp, _ = _load()
    assert recover(inp) == recover(inp)
