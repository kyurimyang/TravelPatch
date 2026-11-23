from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.routers.deps import get_places_client
from app.services.places_client import OpeningPeriod, PlaceDetails
from tests.engine.helpers import load_scenario_a

client = TestClient(app)


class OnePlace:
    def __init__(self, periods=None) -> None:
        self.periods = periods

    def details(self, place_id: str) -> PlaceDetails:
        return PlaceDetails(
            place_id=place_id, lat=35.66, lng=139.70, time_zone="Asia/Tokyo", periods=self.periods
        )


def _plan(day_date=None) -> dict:
    a = load_scenario_a()
    day = a.day.model_copy(update={"date": day_date})
    return {
        "day": day.model_dump(mode="json"),
        "activities": [x.model_dump(mode="json") for x in a.activities],
        "preferences": [x.model_dump(mode="json") for x in a.preferences],
        "travel": [x.model_dump(mode="json") for x in a.travel],
        "warnings": [],
    }


def _add(places, plan=None) -> dict:
    app.dependency_overrides[get_places_client] = lambda: places
    body = {
        "plan": plan or _plan(),
        "place_id": "ChIJteamlab",
        "title": "팀랩",
        "duration": 90,
        "now": 600,
    }
    return client.post("/plans/add-place", json=body)


def test_a_picked_place_becomes_a_must_visit_that_recovers():
    res = _add(OnePlace())
    assert res.status_code == 200
    body = res.json()
    ev = body["event"]
    assert ev["type"] == "MUST_VISIT" and ev["duration"] == 90 and ev["min_duration"] == 45
    assert body["hours"] == "unknown" and ev["open_at"] is None
    # The answer goes straight into POST /recoveries: travel is complete with the new node.
    plan = _plan()
    rec = {
        **{k: plan[k] for k in ("day", "activities", "preferences")},
        "travel": body["travel"],
        "event": ev,
    }
    out = client.post("/recoveries", json=rec).json()
    assert out["candidates"] and all(
        [c["op"] for c in cand["changes"] if c["activity_id"] == ev["activity_id"]] == ["add"]
        for cand in out["candidates"]
    )


def test_a_place_closed_that_day_says_so_instead_of_an_event():
    # 2026-11-23 is a Monday; open only on Sundays (Google day 0).
    sunday_only = (OpeningPeriod(open_day=0, open_minute=600, close_day=0, close_minute=1080),)
    res = _add(OnePlace(sunday_only), _plan(date(2026, 11, 23)))
    assert res.json()["hours"] == "closed" and res.json()["event"] is None
