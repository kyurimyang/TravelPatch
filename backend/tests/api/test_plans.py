from fastapi.testclient import TestClient

from app.main import app
from app.routers.deps import get_places_client
from tests.services.test_plan_builder import FakePlaces, _places, _request

client = TestClient(app)


def _post(places) -> object:
    app.dependency_overrides[get_places_client] = lambda: places
    return client.post("/plans/build", json=_request().model_dump(mode="json"))


def test_build_returns_engine_pieces():
    res = _post(_places())
    assert res.status_code == 200
    body = res.json()
    assert [a["id"] for a in body["activities"]] == ["meiji", "ramen", "sky"]
    assert body["day"]["date"] == "2026-11-20" and body["day"]["travel_mode"] == "transit"
    assert len(body["travel"]) == 6


def test_google_failure_is_a_bad_gateway():
    assert _post(FakePlaces({}, fail={"sky"})).status_code == 502


def test_an_item_ending_before_it_starts_is_rejected():
    body = _request().model_dump(mode="json")
    body["items"][0]["end"] = body["items"][0]["start"]
    app.dependency_overrides[get_places_client] = lambda: _places()
    assert client.post("/plans/build", json=body).status_code == 422
