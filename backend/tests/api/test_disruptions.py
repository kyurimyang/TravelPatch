import pytest
from fastapi.testclient import TestClient

from app.llm.disruption_interpreter import InterpretedDisruption, InterpretedMessage
from app.llm.provider import LLMOutputError
from app.main import app
from app.routers.deps import get_interpret_provider
from tests.engine.helpers import load_scenario_a


class FakeProvider:
    def __init__(self, answer: InterpretedMessage | Exception) -> None:
        self.answer = answer

    def complete_json(self, *, system, user, schema):
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def _event(**fields) -> InterpretedDisruption:
    base = dict.fromkeys(InterpretedDisruption.model_fields)
    return InterpretedDisruption(**{**base, "type": "UNKNOWN", **fields})


def _msg(*events, wishes=()) -> InterpretedMessage:
    # A wish counts only when its evidence is in the text sent (the fixture's text says "실내에서").
    heard = [{"wish": w, "evidence": "실내에서"} for w in wishes]
    return InterpretedMessage(events=list(events), wishes=heard)


@pytest.fixture
def ask():
    """POST /disruptions/interpret with the LLM answering `answer`."""
    inp = load_scenario_a()
    body = {
        "text": "아무 문장, 실내에서",
        "now": 540,
        "location_id": "hotel",
        "activities": [a.model_dump(mode="json") for a in inp.activities],
    }

    def call(answer):
        app.dependency_overrides[get_interpret_provider] = lambda: FakeProvider(answer)
        try:
            return TestClient(app).post("/disruptions/interpret", json=body)
        finally:
            app.dependency_overrides.clear()

    call.titles = {a.id: a.title for a in inp.activities}
    call.body = body
    return call


def test_delay_returns_event_and_chip(ask):
    res = ask(_msg(_event(type="DELAY", delay_minutes=120)))
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok" and body["problem"] is None
    assert body["event"]["type"] == "DELAY" and body["event"]["start_time"] == 660
    assert body["chips"] == ["11:00부터 움직일 수 있어요"]
    assert body["items"][0]["draft"]["delay_minutes"] == 120


def test_closure_chip_uses_the_activity_title_from_the_request(ask):
    some_id, some_title = next(iter(ask.titles.items()))
    body = ask(_msg(_event(type="CLOSURE", activity_hint=some_title))).json()
    assert body["status"] == "ok" and body["event"]["activity_id"] == some_id
    assert body["chips"] == [f"{some_title} 이용 불가"]


def test_unmatched_place_asks_in_words_with_the_places_as_choices(ask):
    body = ask(_msg(_event(type="CLOSURE", activity_hint="존재하지않는곳"))).json()
    assert body["status"] == "needs_input" and body["event"] is None
    assert body["problem"]["code"] == "NO_MATCH"
    assert body["problem"]["detail"] == "어디가 문을 닫았나요?"
    question = body["items"][0]["question"]
    assert question["kind"] == "place" and set(question["candidates"]) <= set(ask.titles)


def test_rain_with_no_time_and_a_moved_booking_both_come_back(ask):
    body = ask(
        _msg(
            _event(type="WEATHER", whole_day=True),
            _event(type="RESERVATION_CHANGE", activity_hint="시부야 스카이", shift_minutes=-60),
            wishes=["indoor"],
        )
    ).json()
    assert body["status"] == "ok"
    assert [e["type"] for e in body["events"]] == ["WEATHER", "RESERVATION_CHANGE"]
    assert body["chips"] == [
        "지금(09:00)부터 비 · 하루 종일",
        "시부야 스카이 예약 17:00 → 16:00",
        "실내 위주로 · 야외 조각은 실내 장소를 먼저 찾아요",
    ]
    assert body["wishes"] == ["indoor"]
    assert body["wish_chips"] == [
        {"wish": "indoor", "text": "실내 위주로 · 야외 조각은 실내 장소를 먼저 찾아요"}
    ]


def test_one_missing_value_does_not_fail_the_rest(ask):
    body = ask(_msg(_event(type="WEATHER"), _event(type="WAIT", activity_hint="라멘"))).json()
    assert body["status"] == "needs_input"
    assert [e["type"] for e in body["events"]] == ["WEATHER"]  # understood, shown as a chip
    assert body["chips"] == ["지금(09:00)부터 비 · 끝나는 시각 미정"]
    assert body["problem"]["detail"] == "라멘 점심에서 얼마나 기다려야 하나요?"


def test_answering_the_question_through_build_needs_no_llm(ask):
    first = ask(_msg(_event(type="WEATHER"), _event(type="WAIT", activity_hint="라멘"))).json()
    drafts = [i["draft"] for i in first["items"]]
    drafts[1]["wait_minutes"] = 40
    body = {k: v for k, v in ask.body.items() if k != "text"} | {"drafts": drafts}
    res = TestClient(app).post("/disruptions/build", json=body)  # no provider override needed
    assert res.status_code == 200
    out = res.json()
    assert out["status"] == "ok" and out["chips"][1] == "라멘 점심 대기 40분"


def test_a_wish_alone_is_enough(ask):
    body = ask(_msg(wishes=["indoor"])).json()
    assert body["status"] == "ok" and body["event"]["type"] == "DELAY"
    assert body["event"]["start_time"] == 540 and body["wishes"] == ["indoor"]


def test_llm_failure_hands_over_to_the_user_instead_of_erroring(ask):
    res = ask(LLMOutputError("refused"))
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "needs_input"
    assert body["problem"]["code"] == "LLM_FAILED"
    assert body["items"][0]["question"]["kind"] == "type"


def test_must_visit_is_reported_unsupported(ask):
    body = ask(_msg(_event(type="MUST_VISIT", activity_hint="도쿄타워"))).json()
    assert body["problem"]["code"] == "UNSUPPORTED"


def test_empty_text_is_rejected_by_validation():
    res = TestClient(app).post(
        "/disruptions/interpret", json={"text": "", "now": 0, "activities": []}
    )
    assert res.status_code == 422
