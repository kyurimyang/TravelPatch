"""Real OpenAI calls. Run with: pytest -m live tests/llm/test_live_interpreter.py"""

import pytest

from app.llm.disruption_interpreter import interpret
from app.llm.provider import OpenAIProvider
from app.schemas.enums import Category
from app.schemas.models import Activity
from app.services.disruption_service import drafts_from, respond

pytestmark = pytest.mark.live

NOW = 9 * 60


def _act(id_: str, title: str) -> Activity:
    return Activity(
        id=id_,
        title=title,
        category=Category.SIGHTSEEING,
        lat=35.0,
        lng=139.0,
        planned_start=600,
        planned_end=660,
        min_duration=30,
    )


ACTS = [
    _act("harajuku", "하라주쿠 다케시타 거리"),
    _act("ramen", "이치란 라멘"),
    _act("izakaya", "시부야 이자카야").model_copy(
        update={"planned_start": 1170, "planned_end": 1260, "reservation_time": 1170}
    ),
]

# (text, expected type, expected event fields)
CASES = [
    ("늦잠 잤어 2시간 늦어", "DELAY", {"start_time": NOW + 120}),
    ("12시부터 비 온대", "WEATHER", {"start_time": 720}),
    ("이자카야 임시휴무래", "CLOSURE", {"activity_id": "izakaya"}),
    ("친구가 너무 힘들어해서 많이 못 걸어", "FATIGUE", {}),
    ("하라주쿠 30분 더 있고 싶어", "EXTEND", {"activity_id": "harajuku", "extra_minutes": 30}),
    ("이자카야 예약이 1시간 앞당겨졌어", "RESERVATION_CHANGE", {"new_time": 1170 - 60}),
    ("라멘집 대기가 40분이래", "WAIT", {"activity_id": "ramen", "minutes": 40}),
]


@pytest.fixture(scope="module")
def provider():
    return OpenAIProvider()


@pytest.mark.parametrize(("text", "expected_type", "fields"), CASES)
def test_text_becomes_the_expected_event(provider, text, expected_type, fields):
    message = interpret(provider, text)
    drafts, wishes = drafts_from(message)
    res = respond(drafts, wishes, now=NOW, location_id="hotel", activities=ACTS)
    assert res.event is not None and res.event.type == expected_type, message
    for name, value in fields.items():
        assert getattr(res.event, name) == value, (message, res.event)


def test_one_sentence_with_three_events(provider):
    text = "비가 많이 오고 있어. 이자카야 예약이 1시간 앞당겨졌고, 라멘집 대기가 40분이야"
    drafts, wishes = drafts_from(interpret(provider, text))
    res = respond(drafts, wishes, now=NOW, location_id="hotel", activities=ACTS)
    assert sorted(e.type for e in res.events) == ["RESERVATION_CHANGE", "WAIT", "WEATHER"]
