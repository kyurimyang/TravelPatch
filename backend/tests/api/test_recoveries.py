import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.engine.helpers import load_scenario_a, scenario_a_with_unsupported_event

client = TestClient(app)
SCENARIOS = Path(__file__).parents[1] / "scenarios"


def _body(name: str) -> dict:
    raw = json.loads((SCENARIOS / name).read_text(encoding="utf-8"))
    raw.pop("expected", None)
    return raw


def test_returns_valid_candidates_with_the_solver_time_filled_in() -> None:
    res = client.post("/recoveries", json=load_scenario_a().model_dump(mode="json"))
    assert res.status_code == 200
    body = res.json()
    assert len(body["candidates"]) >= 1
    assert body["blockers"] == []
    for c in body["candidates"]:
        assert c["violations"] == 0
        assert c["solver_ms"] > 0  # the engine leaves 0; the service layer measures it


def test_same_input_gives_the_same_candidates() -> None:
    body = load_scenario_a().model_dump(mode="json")
    first = client.post("/recoveries", json=body).json()["candidates"]
    second = client.post("/recoveries", json=body).json()["candidates"]

    def strip_time(cs: list[dict]) -> list[dict]:
        return [{k: v for k, v in c.items() if k != "solver_ms"} for c in cs]

    assert strip_time(first) == strip_time(second)


def test_no_valid_plan_comes_back_with_the_reason() -> None:
    # a0 is a reserved must at 9:55; a delay until 10:25 makes that impossible.
    res = client.post("/recoveries", json=_body("eval50/i02_delay.json"))
    assert res.status_code == 200
    body = res.json()
    assert body["candidates"] == []
    assert [(b["kind"], b["activity_id"]) for b in body["blockers"]] == [("reserved_in_past", "a0")]


def test_malformed_input_is_rejected() -> None:
    bad = _body("scenario_a.json")
    bad["preferences"] = bad["preferences"][:-1]  # an activity without a preference
    assert client.post("/recoveries", json=bad).status_code == 422


@pytest.mark.parametrize("kind", ["MUST_VISIT"])  # RESERVATION_CHANGE: supported (scenario F)
def test_an_unsupported_event_is_answered_with_501(kind: str) -> None:
    body = scenario_a_with_unsupported_event(kind).model_dump(mode="json")
    res = client.post("/recoveries", json=body)
    assert res.status_code == 501
    assert kind in res.json()["detail"]


def _noon_rain() -> dict:
    body = load_scenario_a().model_dump(mode="json")
    body["event"] = {"type": "WEATHER", "occurred_at": 720, "start_time": 720, "location_id": "omotesando"}
    return body


def test_visited_places_are_taken_out_on_the_server() -> None:
    # Limit 8 (2026-11-22): the app sends the ticked ids; the server removes them before the
    # engine, and used_input (what restore / lock send back) no longer has them.
    res = client.post("/recoveries", json={**_noon_rain(), "visited": ["meiji", "harajuku"]})
    assert res.status_code == 200
    body = res.json()
    assert body["candidates"]
    assert {a["id"] for a in body["used_input"]["activities"]} & {"meiji", "harajuku"} == set()


def test_without_visited_the_request_is_as_before() -> None:
    res = client.post("/recoveries", json=_noon_rain())
    assert res.status_code == 200
    assert res.json()["candidates"] == []  # the morning left in: no plan (A1)


def test_an_unknown_visited_id_is_rejected() -> None:
    res = client.post("/recoveries", json={**_noon_rain(), "visited": ["nowhere"]})
    assert res.status_code == 422
