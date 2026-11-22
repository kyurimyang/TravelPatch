"""Where each item is (step 2b): address, the larger place it is within, the item before it."""

import json
from pathlib import Path

import pytest

from app.llm.parser import ParsedDay, ParsedItem, ParsedItinerary
from app.services.itinerary_blocks import squash
from app.services.itinerary_draft import build_draft

FIXTURES = Path(__file__).parent.parent / "fixtures" / "paste"
# Real parser answers for the same paste, recorded on different runs (they differ a little).
RECORDINGS = ["tokyo_4days.parsed_v2.json", "tokyo_4days.parsed_v3.json"]


def _item(title="x", **fields) -> ParsedItem:
    base = {
        "title": title,
        "start": None,
        "end": None,
        "category": "sightseeing",
        "role": "activity",
        "reserved": False,
        "note": None,
        "place_query": None,
        "address": None,
        "within": None,
        "spot": None,
        "patch": None,
    }
    return ParsedItem(**{**base, **fields})


def _day(*items: ParsedItem, theme: str | None = None, text: str | None = None):
    parsed = ParsedItinerary(days=[ParsedDay(day_label=None, theme=theme, items=list(items))])
    return build_draft(parsed, text).days[0]


def _places(day) -> list[tuple]:
    return [(i.place_source, i.place_of, i.place_query) for i in day.items]


PARK = _item(
    "Tokyo Disneyland (도쿄 디즈니랜드)", start="09:00", end="12:00", place_query="Tokyo Disneyland"
)


def test_lodging_is_at_the_hotel():
    day = _day(
        _item("체크인", start="15:00", role="lodging", place_query="워싱턴 호텔"),
        _item("a", start="16:00", place_query="a"),
    )
    assert _places(day)[0] == ("hotel", None, None)


def test_a_written_address_is_kept_with_the_name():
    day = _day(
        _item("Fumotoya", start="13:00", place_query="Fumotoya", address="2-2-1 Nishi-Shinjuku"),
        text="13:00~14:00\nFumotoya\n주소: 2-2-1 Nishi-Shinjuku",
    )
    assert _places(day) == [("written", None, "Fumotoya")]
    assert day.items[0].address == "2-2-1 Nishi-Shinjuku"


def test_an_address_not_in_the_text_is_dropped():
    day = _day(
        _item("Fumotoya", start="13:00", place_query="Fumotoya", address="1-1 Somewhere"),
        text="13:00~14:00\nFumotoya",
    )
    assert day.items[0].address is None


def test_within_an_earlier_item_shares_its_place():
    day = _day(
        PARK,
        _item(
            "Queen of Hearts",
            start="12:00",
            place_query="Queen of Hearts",
            within="Tokyo Disneyland",
            note="위치: Tokyo Disneyland Fantasyland",
        ),
    )
    assert _places(day)[1] == ("venue", 0, None)


def test_within_follows_the_chain_to_the_first_item():
    day = _day(
        PARK,
        _item("어트랙션", start="12:00", within="Tokyo Disneyland"),
        _item("간식", start="13:00"),
    )
    assert [p[:2] for p in _places(day)] == [("written", None), ("venue", 0), ("previous", 0)]


def test_within_a_name_not_written_that_day_is_ignored():
    day = _day(
        PARK,
        _item("점심 스시 잔마이", start="12:00", place_query="스시 잔마이", within="Ueno Park"),
    )
    assert _places(day)[1] == ("written", None, "스시 잔마이")


def test_within_is_not_carried_across_a_leg():
    day = _day(
        PARK,
        _item("이동", start="12:00", end="13:00", role="transport", place_query="Tokyo Disneyland"),
        _item("점심 Ikspiari", start="13:00", within="Tokyo Disneyland", place_query="Ikspiari"),
    )
    assert _places(day)[1] == ("written", None, "Ikspiari")


def test_within_with_no_earlier_item_searches_the_larger_place():
    day = _day(
        _item("어트랙션 이용", start="09:00", within="도쿄 디즈니랜드"),
        theme="도쿄 디즈니랜드 종일 관광",
    )
    assert _places(day) == [("venue", None, "도쿄 디즈니랜드")]


def test_no_name_and_no_leg_takes_the_place_before():
    day = _day(PARK, _item("산책", start="12:00"))
    assert _places(day)[1] == ("previous", 0, None)


def test_no_name_after_a_leg_is_left_for_the_user_not_searched_by_title():
    day = _day(
        PARK,
        _item("이동", start="12:00", end="12:30", role="transport"),
        _item("점심 - 스시", start="12:30"),
    )
    assert _places(day)[1] == ("none", None, None)


def test_the_first_item_without_a_name_is_at_the_hotel_the_day_starts_from():
    assert _places(_day(_item("기상 및 조식", start="07:00")))[0] == ("hotel", None, None)


def test_the_item_after_the_hotel_without_a_name_is_at_the_hotel():
    day = _day(_item("체크인", start="15:00", role="lodging"), _item("휴식", start="15:30"))
    assert _places(day)[1] == ("hotel", None, None)


def test_a_name_not_written_in_the_block_is_not_searched():
    day = _day(_item("점심 - 스시", start="12:00", place_query="스시 잔마이"))
    assert _places(day)[0] == ("hotel", None, None)


# --- the recorded 4-day paste against the reviewed answer -------------------------------


@pytest.mark.parametrize("recording", RECORDINGS)
def test_recorded_tokyo_paste_places_like_the_answer(recording):
    text = (FIXTURES / "tokyo_4days.txt").read_text(encoding="utf-8")
    parsed = ParsedItinerary.model_validate_json((FIXTURES / recording).read_text(encoding="utf-8"))
    expected = json.loads((FIXTURES / "tokyo_4days.expected.json").read_text(encoding="utf-8"))
    draft = build_draft(parsed, text)

    for got, want in zip(draft.days, expected["days"], strict=True):
        for i, (item, wanted) in enumerate(zip(got.items, want["items"], strict=True)):
            where = f'{want["day_label"]} #{i} {item.title}'
            place = wanted["place"]
            assert item.place_source == place["source"], where
            if place["source"] == "written":
                assert squash(place["name"]) in squash(item.place_query or ""), where
                assert item.address == place["address"], where
            if place["source"] == "venue":
                root = got.items[item.place_of]
                assert squash(place["name"]) in squash(root.place_query or ""), where
