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
    base = {
        "end": None,
        "category": "sightseeing",
        "reserved": False,
        "note": None,
        "place_query": None,
        "patch": None,
        "role": "activity",
        "address": None,
        "within": None,
        "spot": None,
    }
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
                theme=None,
                items=[
                    _item("하라주쿠", "10:00", end="11:30", patch="market"),
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
    assert [i["patch"] for i in items] == ["market", None]


def test_issues_come_through_for_the_confirm_screen():
    parsed = ParsedItinerary(days=[ParsedDay(day_label=None, theme=None, items=[_item("메이지 신궁", None)])])
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


# --- an answer that stops early (decision 2026-11-23: a remark line ended the plan) ---------

FOUR_DAYS = "".join(f"DAY {d}\n09:00~10:00\na{d}\n11:00~12:00\nb{d}\n" for d in range(1, 5))


def _days(n: int) -> ParsedItinerary:
    return ParsedItinerary(
        days=[
            ParsedDay(
                day_label=f"DAY {d}",
                theme=None,
                items=[_item(f"a{d}", "09:00", end="10:00"), _item(f"b{d}", "11:00", end="12:00")],
            )
            for d in range(1, n + 1)
        ]
    )


class SeqProvider:
    """Gives its answers in turn: the first call gets the first one."""

    def __init__(self, *answers: ParsedItinerary | Exception) -> None:
        self.answers = list(answers)
        self.calls = 0

    def complete_json(self, *, system, user, schema):
        answer = self.answers[min(self.calls, len(self.answers) - 1)]
        self.calls += 1
        if isinstance(answer, Exception):
            raise answer
        return answer


def _post_seq(text: str, *answers) -> tuple[object, SeqProvider]:
    fake = SeqProvider(*answers)
    app.dependency_overrides[get_provider] = lambda: fake
    try:
        return TestClient(app).post("/itineraries/parse", json={"text": text}), fake
    finally:
        app.dependency_overrides.clear()


def test_an_answer_that_reads_most_of_the_text_is_not_asked_again():
    res, fake = _post_seq(FOUR_DAYS, _days(4))
    assert fake.calls == 1 and res.json()["partial"] is None


def test_an_answer_that_stops_early_is_asked_once_more():
    res, fake = _post_seq(FOUR_DAYS, _days(1), _days(4))
    body = res.json()
    assert fake.calls == 2
    assert len(body["draft"]["days"]) == 4 and body["partial"] is None


def test_short_twice_keeps_the_longer_answer_and_says_how_much_was_read():
    res, fake = _post_seq(FOUR_DAYS, _days(2), _days(1))
    body = res.json()
    assert fake.calls == 2 and body["status"] == "ok"
    assert len(body["draft"]["days"]) == 2
    assert body["partial"] == {"read": 4, "written": 8}


def test_a_failed_second_try_keeps_the_first_answer():
    res, _ = _post_seq(FOUR_DAYS, _days(1), LLMOutputError("x"))
    body = res.json()
    assert body["status"] == "ok" and len(body["draft"]["days"]) == 1
    assert body["partial"] == {"read": 2, "written": 8}
