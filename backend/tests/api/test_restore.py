import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.enums import Op
from tests.engine.helpers import load_scenario_a, scenario_a_with_unsupported_event

client = TestClient(app)
SCENARIOS = Path(__file__).parents[1] / "scenarios"


def _body(**extra: str) -> dict:
    return {"input": load_scenario_a().model_dump(mode="json"), **extra}


def _candidate(strategy: str) -> dict:
    res = client.post("/recoveries", json=load_scenario_a().model_dump(mode="json"))
    return next(c for c in res.json()["candidates"] if c["strategy"] == strategy)


def test_keeping_a_dropped_activity_returns_the_price() -> None:
    base = _candidate("relaxed")
    res = client.post(
        "/recoveries/restore", json=_body(strategy="relaxed", activity_id="omotesando")
    )
    assert res.status_code == 200
    cf = res.json()["counterfactual"]
    assert cf["restored_id"] == "omotesando"
    changes = {c["activity_id"]: c for c in cf["result"]["changes"]}
    assert changes["omotesando"]["op"] != Op.DROP
    assert cf["result"]["violations"] == 0
    # The numbers are differences against the candidate the user was looking at.
    assert cf["d_preservation"] == pytest.approx(
        cf["result"]["preservation_rate"] - base["preservation_rate"]
    )
    assert cf["result"]["solver_ms"] > 0  # the service layer times it


def test_the_other_changes_this_causes_are_listed() -> None:
    res = client.post(
        "/recoveries/restore", json=_body(strategy="relaxed", activity_id="omotesando")
    )
    effects = res.json()["counterfactual"]["side_effects"]
    assert effects  # keeping omotesando costs something elsewhere
    assert "omotesando" not in {e["activity_id"] for e in effects}


def test_an_activity_that_is_not_dropped_cannot_be_restored() -> None:
    res = client.post("/recoveries/restore", json=_body(strategy="relaxed", activity_id="meiji"))
    assert res.status_code == 422
    assert "meiji" in res.json()["detail"]


def test_a_strategy_with_no_candidate_is_not_found() -> None:
    res = client.post("/recoveries/restore", json=_body(strategy="nope", activity_id="omotesando"))
    assert res.status_code == 404


def test_restore_works_on_a_day_with_an_added_place() -> None:
    # MUST_VISIT is solved since 2026-11-23 (it was a 501): "what if I keep X" works there too.
    inp = scenario_a_with_unsupported_event("MUST_VISIT").model_dump(mode="json")
    cands = client.post("/recoveries", json=inp).json()["candidates"]
    dropped = next(
        (
            (c["strategy"], x["activity_id"])
            for c in cands
            for x in c["changes"]
            if x["op"] == "drop"
        ),
        None,
    )
    if dropped is None:
        return  # nothing dropped on this day: nothing to restore
    body = {"input": inp, "strategy": dropped[0], "activity_id": dropped[1]}
    assert client.post("/recoveries/restore", json=body).status_code == 200


def test_when_no_valid_plan_keeps_it_the_answer_is_null_not_an_error() -> None:
    # Common: in the eval50 set, about half of all dropped activities cannot be kept at all.
    raw = json.loads((SCENARIOS / "eval50/i00_delay.json").read_text(encoding="utf-8"))
    raw.pop("expected", None)
    res = client.post(
        "/recoveries/restore", json={"input": raw, "strategy": "balanced", "activity_id": "a2"}
    )
    assert res.status_code == 200
    assert res.json() == {"counterfactual": None}
