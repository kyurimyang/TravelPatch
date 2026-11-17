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
    assert [s["title"] for s in body["used_input"]["substitutes"]] == ["가게 p1"]


def test_without_keys_a_closure_still_answers_with_the_blocker():
    body = client.post("/recoveries", json=_closed_izakaya().model_dump(mode="json")).json()
    assert body["candidates"] == []
    assert [b["kind"] for b in body["blockers"]] == ["closed_no_substitute"]
