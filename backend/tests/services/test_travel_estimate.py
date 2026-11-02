from app.engine.recover import recover
from app.engine.validator import validate
from app.schemas.models import HOTEL_ID, TravelTime
from app.schemas.recovery import RecoveryInput
from app.services.travel_estimate import estimate_minutes, fill_missing_travel, haversine_km
from tests.engine.helpers import load_scenario_a

SHINJUKU = (35.6896, 139.7006)
SHIBUYA = (35.6585, 139.7021)


def test_haversine_matches_known_distance() -> None:
    # Shinjuku station area to Shibuya Sky is about 3.5 km as the crow flies
    assert 3.0 < haversine_km(SHINJUKU, SHIBUYA) < 4.0


def test_estimate_is_symmetric_multiple_of_five_and_grows_with_distance() -> None:
    near, far = (35.6590, 139.7010), SHINJUKU
    assert estimate_minutes(SHIBUYA, far) == estimate_minutes(far, SHIBUYA)
    assert estimate_minutes(SHIBUYA, near) % 5 == 0
    assert estimate_minutes(SHIBUYA, near) < estimate_minutes(SHIBUYA, far)
    assert estimate_minutes(SHIBUYA, SHIBUYA) == 5  # never zero for distinct places


def test_known_pairs_are_kept_and_missing_pairs_filled() -> None:
    points = {"hotel": SHINJUKU, "a": SHIBUYA, "b": (35.6590, 139.7010)}
    known = (TravelTime(a="b", b="hotel", minutes=45, source="api"),)
    table = fill_missing_travel(points, known)
    by_pair = {frozenset((t.a, t.b)): t for t in table}
    assert len(table) == 3
    assert by_pair[frozenset(("hotel", "b"))].minutes == 45
    assert by_pair[frozenset(("hotel", "b"))].source == "api"
    assert by_pair[frozenset(("a", "b"))].source == "estimate"


def test_fill_is_deterministic() -> None:
    points = {"hotel": SHINJUKU, "a": SHIBUYA, "b": (35.6590, 139.7010)}
    assert fill_missing_travel(points) == fill_missing_travel(dict(reversed(points.items())))


def test_engine_works_on_a_fully_estimated_table() -> None:
    inp = load_scenario_a()
    points = {a.id: (a.lat, a.lng) for a in inp.activities}
    points[HOTEL_ID] = (inp.day.end_lat, inp.day.end_lng)
    estimated = inp.model_copy(update={"travel": fill_missing_travel(points)})
    RecoveryInput.model_validate(estimated.model_dump())  # complete table passes validation
    results = recover(estimated)
    for r in results:
        assert validate(estimated, r.changes) == []
