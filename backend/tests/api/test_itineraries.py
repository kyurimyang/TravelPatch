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
# Without day headings the text is one call, read again once when it reads short.

FOUR_DAYS = "".join(f"{d}번째 날\n09:00~10:00\na{d}\n11:00~12:00\nb{d}\n" for d in range(1, 5))


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


# --- a text with day headings is read one day per call (2026-11-23) -------------------------

HEADED = "".join(f"DAY {d}\n09:00~10:00\na{d}\n11:00~12:00\nb{d}\n" for d in range(1, 5))


class DayProvider:
    """Answers each call with the day its text is about; `short` days answer with nothing the
    first time (the early stop), `broken` days fail every time."""

    def __init__(self, short: set[int] = frozenset(), broken: set[int] = frozenset()) -> None:
        self.short, self.broken = set(short), set(broken)
        self.texts: list[str] = []

    def complete_json(self, *, system, user, schema):
        self.texts.append(user)
        d = int(user.split()[1])
        if d in self.broken:
            raise LLMOutputError("x")
        if d in self.short:
            self.short.discard(d)
            return ParsedItinerary(days=[ParsedDay(day_label=f"DAY {d}", theme=None, items=[])])
        return ParsedItinerary(days=_days(4).days[d - 1 : d])


def _post_days(fake: DayProvider):
    app.dependency_overrides[get_provider] = lambda: fake
    try:
        return TestClient(app).post("/itineraries/parse", json={"text": HEADED}).json()
    finally:
        app.dependency_overrides.clear()


def test_each_day_is_its_own_short_call_and_all_days_come_back_in_order():
    fake = DayProvider()
    body = _post_days(fake)
    assert len(fake.texts) == 4 and all(t.count("DAY") == 1 for t in fake.texts)
    assert [d["day_label"] for d in body["draft"]["days"]] == ["DAY 1", "DAY 2", "DAY 3", "DAY 4"]
    assert body["partial"] is None


def test_a_day_that_stops_early_is_asked_again_on_its_own():
    fake = DayProvider(short={2})
    body = _post_days(fake)
    assert len(fake.texts) == 5 and sum(t.startswith("DAY 2") for t in fake.texts) == 2
    assert len(body["draft"]["days"]) == 4 and body["partial"] is None


def test_a_day_that_cannot_be_read_leaves_the_others_and_says_so():
    body = _post_days(DayProvider(broken={3}))
    assert body["status"] == "ok"
    assert [d["day_label"] for d in body["draft"]["days"]] == ["DAY 1", "DAY 2", "DAY 4"]
    assert body["partial"] == {"read": 6, "written": 8}


def test_every_day_failing_asks_for_manual_entry():
    body = _post_days(DayProvider(broken={1, 2, 3, 4}))
    assert body["status"] == "manual" and body["problem"]["code"] == "LLM_FAILED"
