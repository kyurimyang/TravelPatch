import pytest
from fastapi.testclient import TestClient

from app.llm.disruption_interpreter import InterpretedDisruption
from app.llm.provider import LLMOutputError
from app.main import app
from app.routers.disruptions import get_provider
from tests.engine.helpers import load_scenario_a


class FakeProvider:
    def __init__(self, answer: InterpretedDisruption | Exception) -> None:
        self.answer = answer

    def complete_json(self, *, system, user, schema):
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def _interp(**fields) -> InterpretedDisruption:
    base = {
        "type": "UNKNOWN",
        "delay_minutes": None,
        "time_from": None,
        "time_to": None,
        "activity_hint": None,
        "extra_minutes": None,
        "new_time": None,
    }
    return InterpretedDisruption(**{**base, **fields})


@pytest.fixture
def ask():
    """POST /disruptions/interpret with the LLM answering `answer`."""
    inp = load_scenario_a()
    body = {
        "text": "아무 문장",
        "now": 540,
        "location_id": "hotel",
        "activities": [a.model_dump(mode="json") for a in inp.activities],
    }

    def call(answer):
        app.dependency_overrides[get_provider] = lambda: FakeProvider(answer)
        try:
            return TestClient(app).post("/disruptions/interpret", json=body)
        finally:
            app.dependency_overrides.clear()

    call.titles = {a.id: a.title for a in inp.activities}
    return call


def test_delay_returns_event_and_chip(ask):
    res = ask(_interp(type="DELAY", delay_minutes=120))
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok" and body["problem"] is None
    assert body["event"]["type"] == "DELAY" and body["event"]["start_time"] == 660
    assert body["chips"] == ["11:00부터 움직일 수 있어요"]
    assert body["interpretation"]["delay_minutes"] == 120


def test_closure_chip_uses_the_activity_title_from_the_request(ask):
    some_id, some_title = next(iter(ask.titles.items()))
    res = ask(_interp(type="CLOSURE", activity_hint=some_title))
    body = res.json()
    assert body["status"] == "ok" and body["event"]["activity_id"] == some_id
    assert body["chips"] == [f"{some_title} 이용 불가"]


def test_unmatched_place_asks_the_user_with_every_activity_as_a_choice(ask):
    body = ask(_interp(type="CLOSURE", activity_hint="존재하지않는곳")).json()
    assert body["status"] == "needs_input" and body["event"] is None
    assert body["problem"]["code"] == "NO_MATCH"
    assert set(body["problem"]["candidates"]) == set(ask.titles)
    assert body["interpretation"]["type"] == "CLOSURE"  # chips can still show what was heard


def test_missing_number_is_not_guessed(ask):
    body = ask(_interp(type="DELAY")).json()
    assert body["status"] == "needs_input" and body["problem"]["code"] == "MISSING_FIELD"


def test_llm_failure_hands_over_to_the_user_instead_of_erroring(ask):
    res = ask(LLMOutputError("refused"))
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "needs_input" and body["interpretation"] is None
    assert body["problem"]["code"] == "LLM_FAILED"


def test_must_visit_is_reported_unsupported(ask):
    body = ask(_interp(type="MUST_VISIT", activity_hint="도쿄타워")).json()
    assert body["problem"]["code"] == "UNSUPPORTED"


def test_empty_text_is_rejected_by_validation():
    res = TestClient(app).post(
        "/disruptions/interpret", json={"text": "", "now": 0, "activities": []}
    )
    assert res.status_code == 422
