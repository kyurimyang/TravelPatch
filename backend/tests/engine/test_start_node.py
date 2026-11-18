"""Arrival day: the day starts at an airport, not at the hotel (decision 2026-11-18).

The start point is one more node in the travel table (START_ID). It exists only when the day
has start coordinates, and it can only be where the user is now, never where the day ends.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.engine.recover import recover
from app.schemas.models import START_ID
from app.schemas.recovery import RecoveryInput

AIRPORT = (35.5494, 139.7798)  # Haneda
# Minutes, the same to every node: keeps the expectation easy to read.
AIRPORT_TO_ANY = 60


def _raw_a() -> dict:
    path = Path(__file__).parents[1] / "scenarios" / "scenario_a.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop("expected")
    return raw


def _arrival_day(*, with_start: bool = True, start_pairs: bool = True) -> dict:
    """Scenario A, but the flight landed late: the user leaves the airport at 11:00."""
    raw = _raw_a()
    if with_start:
        raw["day"]["start_lat"], raw["day"]["start_lng"] = AIRPORT
    if start_pairs:
        others = ["hotel", *(a["id"] for a in raw["activities"])]
        raw["travel"] += [{"a": START_ID, "b": o, "minutes": AIRPORT_TO_ANY} for o in others]
    raw["event"] = {
        "type": "DELAY",
        "occurred_at": 660,
        "start_time": 660,
        "location_id": START_ID,
    }
    return raw


def test_recovery_from_the_airport_has_no_violations() -> None:
    inp = RecoveryInput.model_validate(_arrival_day())
    results = recover(inp)
    assert results
    assert all(r.violations == 0 for r in results)


def test_first_activity_waits_for_the_trip_from_the_airport() -> None:
    inp = RecoveryInput.model_validate(_arrival_day())
    for r in recover(inp):
        starts = [c.after.start for c in r.changes if c.after is not None]
        assert min(starts) >= 660 + AIRPORT_TO_ANY


def test_start_node_needs_start_coordinates_on_the_day() -> None:
    # No start point on the day: "start" is not a node, so the user cannot be there.
    with pytest.raises(ValidationError, match="unknown current location"):
        RecoveryInput.model_validate(_arrival_day(with_start=False, start_pairs=False))


def test_start_node_needs_its_travel_pairs() -> None:
    with pytest.raises(ValidationError, match="travel table incomplete"):
        RecoveryInput.model_validate(_arrival_day(start_pairs=False))


def test_start_coordinates_come_in_pairs() -> None:
    raw = _raw_a()
    raw["day"]["start_lat"] = AIRPORT[0]
    with pytest.raises(ValidationError, match="start_lat and start_lng"):
        RecoveryInput.model_validate(raw)


def test_a_day_without_start_is_unchanged() -> None:
    # Old inputs (no start point) validate and recover exactly as before.
    raw = _raw_a()
    assert RecoveryInput.model_validate(raw).day.start_lat is None
