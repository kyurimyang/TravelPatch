"""multi30 (2026-11-26): the 10 eval itineraries with several events at once (more_events), as
one sentence can say them. Built by `python -m eval.generate --multi`.

Every candidate must pass the validator with all events checked together; a day with no plan
must say why (a blocker or a relaxation), never come back silently empty.
"""

import json
from pathlib import Path

import pytest

from app.engine.conflict_detector import find_blockers
from app.engine.recover import recover
from app.engine.relax import relaxations
from app.schemas.recovery import RecoveryInput

DIR = Path(__file__).parent / "multi30"
FILES = sorted(DIR.glob("*.json"))


def _load(path: Path) -> RecoveryInput:
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop("expected")
    return RecoveryInput.model_validate(raw)


def test_thirty_scenarios_with_more_than_one_event() -> None:
    assert len(FILES) == 30
    assert all(len(_load(p).events) >= 2 for p in FILES)


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_every_event_is_respected(path: Path) -> None:
    inp = _load(path)
    results = recover(inp)
    for r in results:
        assert r.violations == 0
    if not results:
        assert find_blockers(inp) or relaxations(inp)
