"""Block roles -> items, legs, flights and the day's end (step 2a of the paste structuring)."""

import json
from pathlib import Path

import pytest

from app.llm.parser import ParsedDay, ParsedItem, ParsedItinerary
from app.services.itinerary_draft import build_draft, written_ranges

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


def _draft(*days: list[ParsedItem], text: str | None = None):
    parsed = ParsedItinerary(
        days=[ParsedDay(day_label=None, theme=None, items=list(d)) for d in days]
    )
    return build_draft(parsed, text)


def _leg(leg) -> tuple:
    return (leg.after, leg.before, leg.start, leg.end)


# --- legs -------------------------------------------------------------------------------


def test_transport_between_two_items_becomes_a_leg():
    day = _draft(
        [
            _item("a", start="09:00", end="10:00"),
            _item("이동", start="10:00", end="10:30", role="transport", note="JR"),
            _item("b", start="10:30", end="11:00"),
        ]
    ).days[0]
    assert [i.title for i in day.items] == ["a", "b"]
    assert [_leg(x) for x in day.legs] == [(0, 1, 600, 630)]
    assert day.legs[0].note == "JR"


def test_transport_at_the_start_of_the_day_leaves_from_the_day_start():
    day = _draft(
        [_item("이동", start="09:00", end="09:30", role="transport"), _item("a", start="09:30")]
    ).days[0]
    assert [_leg(x) for x in day.legs] == [(None, 0, 540, 570)]


def test_transport_to_the_hotel_mid_day_is_a_stop_at_the_hotel():
    day = _draft(
        [
            _item("체크인", start="12:00", end="12:30", role="lodging", place_query="워싱턴 호텔"),
            _item("a", start="13:00", end="14:00"),
            _item(
                "워싱턴 호텔까지 이동 및 짐 보관",
                start="14:00",
                end="14:30",
                role="transport",
                place_query="워싱턴 호텔",
            ),
            _item("b", start="15:00", end="16:00"),
        ]
    ).days[0]
    assert [(i.title, i.role) for i in day.items][2] == (
        "워싱턴 호텔까지 이동 및 짐 보관",
        "lodging",
    )
    assert day.legs == ()


# --- the day's end ----------------------------------------------------------------------


def test_trailing_transport_and_lodging_set_the_day_end():
    day = _draft(
        [
            _item("a", start="18:00", end="20:30"),
            _item("호텔 복귀", start="20:30", end="21:20", role="transport"),
            _item("호텔 도착 및 휴식", start="21:20", end="22:00", role="lodging"),
        ]
    ).days[0]
    assert [i.title for i in day.items] == ["a"]
    assert [_leg(x) for x in day.legs] == [(0, None, 1230, 1280)]
    assert day.end_time == 22 * 60


def test_a_day_ending_on_an_activity_has_no_written_end():
    assert _draft([_item("a", start="18:00", end="20:00")]).days[0].end_time is None


# --- flights ----------------------------------------------------------------------------


def test_leading_airport_blocks_become_the_arrival_flight():
    day = _draft(
        [
            _item(
                "나리타 국제공항 도착 및 입국 수속",
                start="10:00",
                end="11:00",
                role="airport",
                place_query="나리타 국제공항",
            ),
            _item("a", start="12:00", end="13:00"),
        ]
    ).days[0]
    a = day.arrival
    assert (a.airport_query, a.time, a.buffer_minutes, a.time_written) == (
        "나리타 국제공항",
        600,
        60,
        True,
    )
    assert [i.title for i in day.items] == ["a"]


def test_trailing_airport_blocks_become_the_departure_with_an_unwritten_take_off():
    day = _draft(
        [
            _item("체크아웃", start="07:40", end="08:00", role="lodging"),
            _item(
                "나리타 국제공항 이동",
                start="08:00",
                end="10:30",
                role="transport",
                place_query="나리타 국제공항",
            ),
            _item("체크인", start="10:30", end="11:30", role="airport"),
            _item("탑승 대기", start="12:00", end="12:40", role="airport"),
        ]
    ).days[0]
    d = day.departure
    # Take-off is not written: the last airport block's end stands in, and says so.
    assert (d.airport_query, d.time, d.buffer_minutes, d.time_written) == (
        "나리타 국제공항",
        760,
        130,
        False,
    )
    assert [i.title for i in day.items] == ["체크아웃"]
    assert [_leg(x) for x in day.legs] == [(0, None, 480, 630)]
    assert day.end_time is None  # the flight bounds the day, not the hotel


def test_a_departure_written_as_a_point_in_time_is_taken_as_written():
    day = _draft(
        [
            _item("a", start="09:00", end="10:00"),
            _item("공항 체크인", start="11:00", end="12:00", role="airport"),
            _item("출국편 출발", start="14:00", role="airport"),
        ]
    ).days[0]
    assert (day.departure.time, day.departure.buffer_minutes, day.departure.time_written) == (
        840,
        180,
        True,
    )


def test_an_origin_take_off_before_the_landing_is_absorbed_not_read_as_the_landing():
    day = _draft(
        [
            _item("인천국제공항 출발", start="10:50", role="airport", place_query="인천국제공항"),
            _item("프라하 공항 도착", start="16:20", role="airport", place_query="프라하 공항"),
            _item("입국 심사", start="16:20", end="17:20", role="airport"),
            _item("a", start="19:00", end="20:00"),
        ]
    ).days[0]
    a = day.arrival
    assert (a.airport_query, a.time, a.buffer_minutes) == ("프라하 공항", 980, 60)
    assert len(a.absorbed) == 3 and [i.title for i in day.items] == ["a"]


def test_the_landing_back_home_after_the_take_off_is_absorbed():
    day = _draft(
        [
            _item("a", start="09:00", end="10:00"),
            _item(
                "프라하 공항 체크인",
                start="15:30",
                end="16:30",
                role="airport",
                place_query="프라하 공항",
            ),
            _item("탑승 대기", start="17:30", end="18:00", role="airport"),
            _item("프라하 공항 출발", start="18:30", role="airport"),
            _item("인천국제공항 도착", start="13:10", role="airport", place_query="인천국제공항"),
        ]
    ).days[0]
    d = day.departure
    assert (d.airport_query, d.time, d.buffer_minutes, d.time_written) == (
        "프라하 공항",
        1110,
        180,
        True,
    )
    assert len(d.absorbed) == 4 and [i.title for i in day.items] == ["a"]


def test_a_time_less_landing_back_home_does_not_hide_the_take_off():
    day = _draft(
        [
            _item("a", start="09:00", end="10:00"),
            _item("공항 체크인", start="15:30", end="16:30", role="airport"),
            _item("출발", start="18:30", role="airport"),
            _item("인천 도착", role="airport"),
        ]
    ).days[0]
    assert (day.departure.time, day.departure.time_written) == (1110, True)


def test_a_point_time_line_keeps_the_range_below_it_for_the_next_block():
    text = "16:20\n프라하 도착\n\n16:20~17:20\n입국 심사\n"
    day = _draft(
        [
            _item("프라하 도착", start="16:20", role="airport"),
            _item("입국 심사", start="16:20", role="airport"),
        ],
        text=text,
    ).days[0]
    assert (day.arrival.time, day.arrival.buffer_minutes) == (980, 60)


def test_transport_to_the_hotel_right_before_check_in_stays_a_leg():
    day = _draft(
        [
            _item(
                "공항에서 숙소 이동",
                start="17:20",
                end="18:20",
                role="transport",
                place_query="Hotel Leon D'Oro",
            ),
            _item("Hotel Leon D'Oro 체크인", start="18:20", end="18:50", role="lodging"),
            _item("a", start="19:00", end="20:00"),
        ]
    ).days[0]
    assert [i.title for i in day.items] == ["Hotel Leon D'Oro 체크인", "a"]
    assert [_leg(x) for x in day.legs] == [(None, 0, 1040, 1100)]


def test_airport_blocks_without_a_time_stay_items():
    day = _draft([_item("공항", role="airport"), _item("a", start="12:00")]).days[0]
    assert day.arrival is None and [i.title for i in day.items] == ["공항", "a"]


# --- hotel ------------------------------------------------------------------------------


def test_the_hotel_is_the_place_named_most_by_lodging_and_hotel_bound_transport():
    draft = _draft(
        [_item("체크인", start="16:00", role="lodging", place_query="신주쿠 워싱턴 호텔")],
        [
            _item(
                "호텔 복귀", start="21:00", end="22:00", role="transport", place_query="신주쿠 호텔"
            ),
            _item("이동", start="09:00", role="transport", place_query="신주쿠 워싱턴 호텔"),
        ],
    )
    assert draft.hotel_query == "신주쿠 워싱턴 호텔"


def test_no_hotel_named_gives_none():
    assert _draft([_item("a", start="09:00", place_query="센소지")]).hotel_query is None


# --- titles and the text cross-check ----------------------------------------------------


def test_a_leading_category_label_is_dropped_from_the_title():
    titles = [
        _draft([_item(t, start="12:00")]).days[0].items[0].title
        for t in ("점심 식사: Fumotoya (麓屋)", "관광 및 쇼핑: 나카미세", "센소지", "※ 예약: 19시")
    ]
    assert titles == ["Fumotoya (麓屋)", "나카미세", "센소지", "※ 예약: 19시"]


def test_written_ranges_reads_time_ranges_from_the_text_in_order():
    assert written_ranges("13:00~16:00\n어트랙션\n9:00 - 9:50 이동\n") == [
        ("13:00", "16:00"),
        ("09:00", "09:50"),
    ]


def test_the_same_start_on_two_days_takes_each_day_its_own_range():
    text = "DAY 1\n13:00~14:00\n점심\nDAY 2\n13:00~16:00\n어트랙션"
    draft = _draft([_item("점심", start="13:00")], [_item("어트랙션", start="13:00")], text=text)
    assert [d.items[0].end for d in draft.days] == [840, 960]


def test_an_end_the_model_dropped_is_restored_from_the_text():
    day = _draft([_item("어트랙션 이용", start="13:00")], text="13:00~16:00\n어트랙션 이용").days[0]
    assert (day.items[0].end, day.items[0].duration_estimated) == (960, False)


# --- the recorded 4-day paste against the reviewed answer -------------------------------


def _hhmm(m: int | None) -> str | None:
    return None if m is None else f"{m // 60:02d}:{m % 60:02d}"


def _end_ref(ref):
    return None if ref in ("start", "end") else ref


@pytest.mark.parametrize("recording", RECORDINGS)
def test_recorded_tokyo_paste_splits_like_the_answer(recording):
    text = (FIXTURES / "tokyo_4days.txt").read_text(encoding="utf-8")
    parsed = ParsedItinerary.model_validate_json((FIXTURES / recording).read_text(encoding="utf-8"))
    expected = json.loads((FIXTURES / "tokyo_4days.expected.json").read_text(encoding="utf-8"))
    draft = build_draft(parsed, text)

    assert draft.hotel_query == expected["trip"]["hotel"]["name"]
    for got, want in zip(draft.days, expected["days"], strict=True):
        label = want["day_label"]
        assert [(i.title, i.role, _hhmm(i.start), _hhmm(i.end)) for i in got.items] == [
            (i["title"], i["role"], i["start"], i["end"]) for i in want["items"]
        ], label
        assert [(x.after, x.before, _hhmm(x.start), _hhmm(x.end)) for x in got.legs] == [
            (_end_ref(x["after"]), _end_ref(x["before"]), x["start"], x["end"])
            for x in want["legs"]
        ], label
        want_end = want["end"]["deadline"] if want["end"]["place"] == "hotel" else None
        assert _hhmm(got.end_time) == want_end, label
        for which in ("arrival", "departure"):
            flight, wanted = getattr(got, which), want.get(which)
            if wanted is None:
                assert flight is None, label
            else:
                assert (_hhmm(flight.time), flight.buffer_minutes) == (
                    wanted["time"],
                    wanted["buffer_minutes"],
                ), label
                if "v2" not in recording:  # v2 predates the airport name in the prompt
                    assert flight.airport_query == wanted["airport"]["name"], label


# --- the recorded Prague paste: a flight that leaves from home and lands back home ------

PRAGUE = ["prague_4days.parsed_v1.json", "prague_4days.parsed_v2.json"]


@pytest.mark.parametrize("recording", PRAGUE)
def test_recorded_prague_paste_reads_both_flights(recording):
    text = (FIXTURES / "prague_4days.txt").read_text(encoding="utf-8")
    parsed = ParsedItinerary.model_validate_json((FIXTURES / recording).read_text(encoding="utf-8"))
    draft = build_draft(parsed, text)
    day1, day4 = draft.days[0], draft.days[3]

    assert draft.hotel_query == "Hotel Leon D'Oro"
    a = day1.arrival
    assert (a.airport_query, _hhmm(a.time), a.buffer_minutes) == (
        "프라하 바츨라프 하벨 국제공항",
        "16:20",
        60,
    )
    assert [_leg(x) for x in day1.legs] == [(None, 0, 1040, 1100)]
    assert day1.items[0].role == "lodging" and day1.items[1].title == "Lokál Dlouhááá"

    d = day4.departure
    assert (_hhmm(d.time), d.buffer_minutes, d.time_written) == ("18:30", 180, True)
    assert all(i.role != "airport" for i in day4.items)
    assert all(not day.issues for day in draft.days)
    addresses = [i.address for day in draft.days for i in day.items if i.address]
    assert addresses and not any(x.startswith("주소") for x in addresses)
