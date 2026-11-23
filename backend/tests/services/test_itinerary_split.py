from pathlib import Path

import pytest

from app.services.itinerary_split import is_day_heading, split_days

PASTE = Path(__file__).parents[1] / "fixtures" / "paste"


@pytest.mark.parametrize("name", ["prague_4days.txt", "tokyo_4days.txt"])
def test_a_recorded_four_day_paste_splits_into_its_four_days(name: str) -> None:
    text = (PASTE / name).read_text(encoding="utf-8")
    days = split_days(text)
    assert len(days) == 4
    assert [d.splitlines()[0][:5] for d in days] == ["DAY 1", "DAY 2", "DAY 3", "DAY 4"]
    # Nothing lost or doubled: the days put back together are the text.
    assert "".join("".join(d.split()) for d in days) == "".join(text.split())


def test_the_prague_remark_stays_with_day_one() -> None:
    # The line that made the model stop after day 1 must not start a day of its own.
    days = split_days((PASTE / "prague_4days.txt").read_text(encoding="utf-8"))
    assert "※ 장거리 비행 직후" in days[0]
    assert "DAY 2" not in days[0]


@pytest.mark.parametrize(
    "line",
    [
        "DAY 2. 프라하성",
        "Day 3",
        "day-4 shopping",
        "2일차",
        "3 일차 오사카",
        "2日目",
        "第3天",
        "1월 25일 (월)",
        "## DAY 2",
    ],
)
def test_headings(line: str) -> None:
    assert is_day_heading(line)


@pytest.mark.parametrize(
    "line",
    [
        "10:50",
        "16:20~17:20",
        "Day 2:30 pm",
        "다음 날 13:10",
        "점심 식사: Mincovna",
        "1일 이용권 구매",
    ],
)
def test_not_headings(line: str) -> None:
    assert not is_day_heading(line)


def test_a_text_with_one_heading_or_none_stays_whole() -> None:
    assert split_days("10:00 하라주쿠\n12:00 라멘") == ["10:00 하라주쿠\n12:00 라멘"]
    assert split_days("DAY 1\n10:00 하라주쿠") == ["DAY 1\n10:00 하라주쿠"]


def test_a_preamble_goes_with_the_first_day() -> None:
    days = split_days("도쿄 3박 4일\n\nDAY 1\n10:00 a\nDAY 2\n10:00 b")
    assert days == ["도쿄 3박 4일\n\nDAY 1\n10:00 a", "DAY 2\n10:00 b"]
