from fastapi.testclient import TestClient

from app.main import app
from tests.engine.helpers import load_scenario_a

client = TestClient(app)


def _lock(ids: list[str]):
    body = {"input": load_scenario_a().model_dump(mode="json"), "activity_ids": ids}
    return client.post("/recoveries/lock", json=body)


def test_lock_keeps_the_activity_and_returns_the_locked_input():
    body = _lock(["ramen"]).json()
    for c in body["candidates"]:
        ramen = next(x for x in c["changes"] if x["activity_id"] == "ramen")
        assert ramen["op"] == "keep"
    ramen_in = next(a for a in body["used_input"]["activities"] if a["id"] == "ramen")
    assert ramen_in["reservation_time"] == ramen_in["planned_start"]


def test_locking_something_already_past_says_why():
    body = _lock(["meiji"]).json()
    assert body["candidates"] == []
    assert [(b["kind"], b["activity_id"]) for b in body["blockers"]] == [
        ("reserved_in_past", "meiji")
    ]


def test_unknown_activity_is_422():
    assert _lock(["nope"]).status_code == 422


def test_the_activity_being_extended_cannot_be_locked():
    # "Leave it as it was" would undo the user's own ask; before this the extension silently won
    # and the "locked" piece came back extended (found by the 2026-11-23 property run).
    from tests.engine.generators import random_instance

    inp = random_instance(0)
    assert inp.event.type == "EXTEND"
    body = {"input": inp.model_dump(mode="json"), "activity_ids": [inp.event.activity_id]}
    res = client.post("/recoveries/lock", json=body)
    assert res.status_code == 422
    assert "extended" in res.json()["detail"]
