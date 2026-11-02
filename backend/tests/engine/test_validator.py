from app.engine.validator import validate
from tests.engine.helpers import load_scenario_a as _inp
from tests.engine.helpers import plan as _plan


def _kinds(violations: list) -> list[tuple[str, str]]:
    return [(v.kind, v.activity_id) for v in violations]



def test_documented_solution_is_valid() -> None:
    inp = _inp()
    assert validate(inp, _plan(inp)) == []


def test_travel_violation_when_next_starts_too_early() -> None:
    inp = _inp()
    # meiji ends 730, travel 5, harajuku starts 730: too early
    violations = validate(inp, _plan(inp, harajuku=(730, 780)))
    assert _kinds(violations) == [("travel", "harajuku")]


def test_order_of_changes_does_not_matter() -> None:
    inp = _inp()
    changes = _plan(inp, harajuku=(730, 780))
    assert validate(inp, changes) == validate(inp, tuple(reversed(changes)))


def test_reserved_activity_cannot_move() -> None:
    inp = _inp()
    violations = validate(inp, _plan(inp, sky=(1030, 1090)))
    assert _kinds(violations) == [("reservation", "sky")]


def test_closing_time_is_enforced() -> None:
    inp = _inp()
    closed_early = inp.model_copy(
        update={
            "activities": tuple(
                a.model_copy(update={"close_at": 1000}) if a.id == "cafe" else a
                for a in inp.activities
            )
        }
    )
    assert _kinds(validate(closed_early, _plan(closed_early))) == [("hours", "cafe")]


def test_opening_time_is_enforced() -> None:
    inp = _inp()
    opens_late = inp.model_copy(
        update={
            "activities": tuple(
                a.model_copy(update={"open_at": 980}) if a.id == "cafe" else a
                for a in inp.activities
            )
        }
    )
    assert _kinds(validate(opens_late, _plan(opens_late))) == [("hours", "cafe")]


def test_hotel_return_deadline() -> None:
    inp = _inp()
    # izakaya ends 1260, hotel is 30 min away -> 1290
    strict = inp.model_copy(update={"day": inp.day.model_copy(update={"end_deadline": 1280})})
    assert _kinds(validate(strict, _plan(strict))) == [("deadline", "izakaya")]


def test_minimum_duration_is_enforced() -> None:
    inp = _inp()
    # cafe min is 30 min
    violations = validate(inp, _plan(inp, cafe=(970, 990)))
    assert _kinds(violations) == [("duration", "cafe")]


def test_must_activity_cannot_be_dropped() -> None:
    inp = _inp()
    violations = validate(inp, _plan(inp, ramen=None))
    assert _kinds(violations) == [("must_drop", "ramen")]


def test_missing_change_entry_is_reported() -> None:
    inp = _inp()
    changes = tuple(c for c in _plan(inp) if c.activity_id != "ramen")
    assert _kinds(validate(inp, changes)) == [("coverage", "ramen")]


def test_cannot_start_before_delayed_start_time() -> None:
    inp = _inp()
    # delay: the user can move again at 660; meiji at 600 is in the past
    violations = validate(inp, _plan(inp, meiji=(600, 650)))
    assert _kinds(violations) == [("past", "meiji")]


def test_first_activity_must_be_reachable_from_current_location() -> None:
    inp = _inp()
    # now = 660, hotel -> meiji is 20 min, so meiji at 666 is unreachable from the hotel
    changes = _plan(inp, meiji=(666, 716))
    assert _kinds(validate(inp, changes)) == [("origin", "meiji")]
