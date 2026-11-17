from fastapi.testclient import TestClient

from app.llm.parser import MAX_TEXT_CHARS, ParsedDay, ParsedItem, ParsedItinerary
from app.llm.provider import LLMOutputError
from app.main import app
from app.routers.deps import get_provider


class FakeProvider:
    def __init__(self, answer: ParsedItinerary | Exception) -> None:
        self.answer = answer
        self.calls = 0

    def complete_json(self, *, system, user, schema):
        self.calls += 1
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def _item(title: str, start: str | None, **fields) -> ParsedItem:
    base = {"end": None, "category": "sightseeing", "reserved": False, "note": None}
    return ParsedItem(title=title, start=start, **{**base, **fields})


def _post(text: str, answer: ParsedItinerary | Exception) -> tuple[object, FakeProvider]:
    fake = FakeProvider(answer)
    app.dependency_overrides[get_provider] = lambda: fake
    try:
        return TestClient(app).post("/itineraries/parse", json={"text": text}), fake
    finally:
        app.dependency_overrides.clear()


def test_parse_returns_draft_in_minutes():
    parsed = ParsedItinerary(
        days=[
            ParsedDay(
                day_label="1일차",
                items=[
                    _item("하라주쿠", "10:00", end="11:30"),
                    _item("라멘 점심", "12:00", category="meal"),
                ],
            )
        ]
    )
    res, _ = _post("1일차\n10:00-11:30 하라주쿠\n12시 라멘 점심", parsed)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok" and body["problem"] is None
    items = body["draft"]["days"][0]["items"]
    assert [(i["title"], i["start"], i["end"]) for i in items] == [
        ("하라주쿠", 600, 690),
        ("라멘 점심", 720, 780),  # meal default 60 minutes
    ]
    assert items[1]["duration_estimated"] is True


def test_issues_come_through_for_the_confirm_screen():
    parsed = ParsedItinerary(days=[ParsedDay(day_label=None, items=[_item("메이지 신궁", None)])])
    res, _ = _post("메이지 신궁", parsed)
    body = res.json()
    assert body["status"] == "ok"
    assert [i["code"] for i in body["draft"]["days"][0]["issues"]] == ["NO_TIME"]


def test_llm_failure_asks_for_manual_entry_not_an_error():
    res, _ = _post("아무 글", LLMOutputError("bad json twice"))
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "manual"
    assert body["draft"] is None
    assert body["problem"]["code"] == "LLM_FAILED"


def test_empty_text_is_rejected_before_the_llm():
    res, fake = _post("   ", ParsedItinerary(days=[]))
    assert res.status_code == 422
    assert fake.calls == 0


def test_too_long_text_is_rejected_before_the_llm():
    res, fake = _post("가" * (MAX_TEXT_CHARS + 1), ParsedItinerary(days=[]))
    assert res.status_code == 422
    assert fake.calls == 0


def test_no_days_found_is_reported():
    res, _ = _post("안녕하세요", ParsedItinerary(days=[]))
    body = res.json()
    assert body["status"] == "manual"
    assert body["problem"]["code"] == "NOTHING_FOUND"
