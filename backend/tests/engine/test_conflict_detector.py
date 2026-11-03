import json
from pathlib import Path

import pytest

from app.engine.conflict_detector import find_blockers
from app.engine.recover import recover
from app.schemas.recovery import RecoveryInput

SCENARIOS = Path(__file__).parents[1] / "scenarios"


def _load(path: Path) -> RecoveryInput:
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop("expected", None)
    return RecoveryInput.model_validate(raw)


def _blockers(name: str) -> list[tuple[str, str, int | None]]:
    return [(b.kind, b.activity_id, b.max_extra_minutes) for b in find_blockers(_load(SCENARIOS / name))]


def test_reserved_must_before_the_user_can_move() -> None:
    # Delayed until 10:25 (625); a0 is a must with a 9:55 reservation.
    assert _blockers("eval50/i02_delay.json") == [("reserved_in_past", "a0", None)]


@pytest.mark.parametrize(
    ("name", "activity"),
    [("i03_weather", "a3"), ("i05_weather", "a5"), ("i07_weather", "a4")],
)
def test_reserved_outdoor_must_in_the_rain(name: str, activity: str) -> None:
    assert _blockers(f"eval50/{name}.json") == [("reserved_in_rain", activity, None)]


def test_extension_that_closing_time_forbids() -> None:
    # a0 closes at 10:05, exactly when it ends: not even 5 more minutes fit.
    assert _blockers("eval50/i04_extend.json") == [("extension_blocked", "a0", 0)]


def test_blockers_report_the_blocking_time_and_requested_extra() -> None:
    (b,) = find_blockers(_load(SCENARIOS / "eval50/i03_weather.json"))
    assert b.blocking_time == 900  # the reservation that cannot move


def test_solvable_scenarios_have_no_blockers() -> None:
    for name in ("scenario_a.json", "scenario_b.json", "scenario_c.json", "scenario_d.json", "scenario_e.json"):
        assert _blockers(name) == []


def test_sound_and_complete_on_the_evaluation_set() -> None:
    # Sound: a reported blocker really means no plan. Complete (on this set): every
    # unsolvable scenario has a reported blocker.
    for path in sorted((SCENARIOS / "eval50").glob("*.json")):
        inp = _load(path)
        unsolvable = not recover(inp)
        assert bool(find_blockers(inp)) == unsolvable, path.stem
