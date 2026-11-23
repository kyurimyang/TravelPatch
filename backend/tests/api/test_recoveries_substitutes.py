from fastapi.testclient import TestClient

from app.main import app
from app.routers.deps import get_places_client_optional, get_provider_optional
from tests.services.test_substitute_finder import FakeLLM, FakePlaces, _closed_izakaya, _details

client = TestClient(app)


def test_closure_without_substitutes_gets_a_searched_substitute():
    inp = _closed_izakaya()
    target = next(a for a in inp.activities if a.id == "izakaya")
    places = FakePlaces({"p1": _details("p1", target.lat + 0.003, target.lng, None)})
    app.dependency_overrides[get_provider_optional] = lambda: FakeLLM()
    app.dependency_overrides[get_places_client_optional] = lambda: places

    body = client.post("/recoveries", json=inp.model_dump(mode="json")).json()

    assert body["blockers"] == []
    change = next(c for c in body["candidates"][0]["changes"] if c["activity_id"] == "izakaya")
    assert change["op"] == "substitute" and change["substitute_id"] == "sub_izakaya_1"
    assert change["needs_check"] is True  # Google gave no hours for it
    # The client gets the substitutes back, with their names, to show and to send again.
    for_closed = [s for s in body["used_input"]["substitutes"] if s["replaces"] == "izakaya"]
    assert [s["title"] for s in for_closed] == ["가게 p1"]


def test_without_keys_a_closure_still_answers_with_the_blocker():
    body = client.post("/recoveries", json=_closed_izakaya().model_dump(mode="json")).json()
    assert body["candidates"] == []
    assert [b["kind"] for b in body["blockers"]] == ["closed_no_substitute"]


def test_a_dropped_piece_gets_a_nearby_place_searched_and_offered():
    # 2026-11-24: not only a closure. A plan that drops a piece searches a similar place near it
    # and solves again; the engine takes it where that changes the day less than the drop.
    from tests.engine.helpers import load_scenario_a

    body = load_scenario_a().model_dump(mode="json")
    body["event"] = {"type": "DELAY", "occurred_at": 540, "start_time": 780, "location_id": "hotel"}
    first = client.post("/recoveries", json=body).json()  # no keys: no search
    dropped = {
        c["activity_id"] for r in first["candidates"] for c in r["changes"] if c["op"] == "drop"
    }
    assert dropped, "the scenario must drop something for this test to mean anything"

    acts = {a["id"]: a for a in body["activities"]}
    near = {
        f"p{i}": _details(f"p{i}", acts[a]["lat"] + 0.002, acts[a]["lng"], None)
        for i, a in enumerate(sorted(dropped))
    }
    places = FakePlaces(near)
    app.dependency_overrides[get_provider_optional] = lambda: FakeLLM()
    app.dependency_overrides[get_places_client_optional] = lambda: places
    out = client.post("/recoveries", json=body).json()

    assert 1 <= len(places.searches) <= 2  # MAX_DROP_SEARCHES
    subs = out["used_input"]["substitutes"]
    assert subs and {s["replaces"] for s in subs} <= dropped
    assert all(c["violations"] == 0 for c in out["candidates"])
