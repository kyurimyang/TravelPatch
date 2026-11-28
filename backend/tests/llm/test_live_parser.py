"""Real OpenAI calls. Run with: pytest -m live tests/llm/test_live_parser.py"""

from pathlib import Path

import pytest

from app.llm.parser import ParsedItinerary, parse_itinerary
from app.llm.provider import OpenAIProvider
from app.routers.itineraries import _parse_text
from app.services.itinerary_draft import build_draft, unread_lines
from app.services.itinerary_split import split_days

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


# ---- 부산 2박 3일 (user paste 2026-11-28): no hotel is written anywhere ----
# Checked on what the user gets (the router's per-day parse with its second try, then the rule
# step), not on one raw model answer: the raw answer drops a different line on each run.

BUSAN = (Path(__file__).parents[1] / "fixtures" / "paste" / "busan_3days.txt").read_text(
    encoding="utf-8"
)


@pytest.fixture(scope="module")
def busan():
    provider = OpenAIProvider()
    parts = [_parse_text(provider, chunk) for chunk in split_days(BUSAN)]
    assert all(p is not None for p in parts)
    parsed = ParsedItinerary(days=[day for p in parts for day in p.days])
    return parsed, build_draft(parsed, BUSAN)


def test_bags_at_a_station_are_not_the_hotel(busan):
    """ "부산역 도착 및 짐 보관" is a stop at the station, not the traveler's lodging: read as
    lodging, the station became the hotel for all three days (invariant 8: no hotel is written)."""
    parsed, draft = busan
    assert parsed.days[0].items[0].role == "activity", parsed.days[0].items[0]
    assert draft.hotel_query is None


def test_busan_loses_no_time_line(busan):
    parsed, draft = busan
    assert len(draft.days) == 3
    assert unread_lines(parsed, BUSAN) == []
    # Each day ends where it is written to: 20:00, 19:30, 20:00.
    assert [d.end_time for d in draft.days] == [20 * 60, 19 * 60 + 30, 20 * 60]
