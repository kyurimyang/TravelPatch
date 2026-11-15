"""Real OpenAI calls. Run with: pytest -m live tests/llm/test_live_parser.py"""

import pytest

from app.llm.parser import parse_itinerary
from app.llm.provider import OpenAIProvider

pytestmark = pytest.mark.live

TEXT = """\
1일차
09:00 아사쿠사 센소지
12:00 점심 - 스시
15:00 시부야 스카이 (예약 완료)
저녁은 근처에서 대충

Day 2
오전 10시 우에노 공원 산책
14:00-16:00 아키하바라 쇼핑
"""


@pytest.fixture(scope="module")
def parsed():
    return parse_itinerary(OpenAIProvider(), TEXT)


def test_splits_days_in_order(parsed):
    assert len(parsed.days) == 2
    assert [d.day_label for d in parsed.days] == ["1일차", "Day 2"]


def test_copies_times_and_never_invents_them(parsed):
    day1, day2 = parsed.days
    assert [i.start for i in day1.items[:3]] == ["09:00", "12:00", "15:00"]
    assert day1.items[3].start is None  # "저녁은 근처에서 대충" has no time
    assert day2.items[0].start == "10:00"
    assert (day2.items[1].start, day2.items[1].end) == ("14:00", "16:00")


def test_reserved_only_when_the_text_says_so(parsed):
    day1 = parsed.days[0]
    assert day1.items[2].reserved is True
    assert not any(i.reserved for i in day1.items[:2])
