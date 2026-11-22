"""midday30 (2026-11-22): the 10 eval itineraries recovered in the middle of the day, the
traveller standing at the place that just ended. Built by `python -m eval.generate --midday`.

Every scenario goes through services/visited.py first, as the app does. The engine must never
bring a visited place back, and every candidate must pass the validator.
"""

import json
from pathlib import Path

import pytest

from app.engine.recover import recover
from app.schemas.models import START_ID
from app.schemas.recovery import RecoveryInput
from app.services.visited import apply_visited

DIR = Path(__file__).parent / "midday30"
FILES = sorted(DIR.glob("*.json"))


def _load(path: Path) -> tuple[RecoveryInput, list[str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop("expected")
    visited = raw.pop("visited")
    return apply_visited(RecoveryInput.model_validate(raw), visited), visited


def test_thirty_scenarios() -> None:
    assert len(FILES) == 30


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_mid_day_recovery(path: Path) -> None:
    inp, visited = _load(path)
    assert inp.event.location_id == START_ID  # standing at a visited place
    for r in recover(inp):
        assert r.violations == 0
        assert not set(visited) & {c.activity_id for c in r.changes}
