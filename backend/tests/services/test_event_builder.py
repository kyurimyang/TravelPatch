import pytest

from app.schemas.disruption import EventDraft
from app.schemas.enums import Category, EventType
from app.schemas.models import Activity
from app.services.event_builder import build_item, built_events, match_activities

NOW = 9 * 60  # 09:00


def _act(id_: str, title: str, category=Category.SIGHTSEEING, start=600, **kw) -> Activity:
    return Activity(
        id=id_,
        title=title,
        category=category,
        lat=35.0,
        lng=139.0,
        planned_start=start,
        planned_end=start + 60,
        min_duration=30,
        **kw,
    )


ACTS = [
    _act("meiji", "메이지 신궁"),
    _act("harajuku", "하라주쿠 다케시타 거리"),
    _act("omotesando", "오모테산도 산책"),
    _act("ramen", "이치란", Category.MEAL, start=750),
    _act("sky", "시부야 스카이", start=1020, reservation_time=1020),
    _act("izakaya", "시부야 이자카야", Category.MEAL, start=1170, reservation_time=1170),
]


def _item(location_id: str = "hotel", **fields):
    return build_item(EventDraft(**fields), now=NOW, location_id=location_id, activities=ACTS)


def _event(**fields):
    item = _item(**fields)
    assert item.event is not None, item.question
    return item.event


def _question(**fields):
    item = _item(**fields)
    assert item.event is None
    return item.question


def test_delay_adds_minutes_to_now():
    event = _event(type="DELAY", delay_minutes=120)
    assert event.type == EventType.DELAY
    assert (event.occurred_at, event.start_time) == (NOW, NOW + 120)
    assert _item(type="DELAY", delay_minutes=120).chip == "11:00부터 움직일 수 있어요"


def test_delay_past_midnight_asks_again():
    assert _question(type="DELAY", delay_minutes=24 * 60).field == "delay_minutes"


def test_delay_without_minutes_starts_now_and_says_so():
    item = _item(type="DELAY")
    assert item.event.start_time == NOW and item.assumed
    assert item.chip == "지금(09:00)부터 움직일 수 있어요"
    assert item.question.kind == "minutes"  # how to correct it


def test_weather_parses_clock_times():
    event = _event(type="WEATHER", time_from="12:00", time_to="15:30")
    assert (event.start_time, event.end_time) == (720, 930)


def test_weather_without_time_is_from_now():
    item = _item(type="WEATHER")
    assert (item.event.start_time, item.event.end_time) == (NOW, None)
    assert item.chip == "지금(09:00)부터 비 · 끝나는 시각 미정" and item.assumed


def test_whole_day_rain_is_from_now_to_the_end_of_the_day():
    item = _item(type="WEATHER", whole_day=True)
    assert (item.event.start_time, item.event.end_time) == (NOW, None)
    assert item.chip == "지금(09:00)부터 비 · 하루 종일"


@pytest.mark.parametrize("bad", ["12시", "25:00", "12:60", "noon"])
def test_weather_bad_time_text_is_asked_in_words(bad):
    q = _question(type="WEATHER", time_from=bad)
    assert (q.field, q.kind, q.text) == ("time_from", "time", "비가 언제부터 오나요?")


def test_weather_end_must_be_after_start():
    assert _question(type="WEATHER", time_from="15:00", time_to="12:00").kind == "time"


def test_closure_matches_activity_by_substring():
    assert _event(type="CLOSURE", activity_hint="이자카야").activity_id == "izakaya"


def test_match_ignores_spaces_and_case():
    assert [a.id for a in match_activities("시부야스카이", ACTS)] == ["sky"]


def test_match_drops_trailing_particles():
    assert [a.id for a in match_activities("시부야 스카이 예약", ACTS)] == ["sky"]


def test_match_by_kind_of_place():
    assert [a.id for a in match_activities("점심 식당", ACTS)] == ["ramen"]
    assert [a.id for a in match_activities("저녁", ACTS)] == ["izakaya"]


def test_ambiguous_hint_asks_with_those_candidates():
    q = _question(type="CLOSURE", activity_hint="시부야")
    assert q.kind == "place" and set(q.candidates) == {"sky", "izakaya"}
    assert q.text == "어디가 문을 닫았나요?"


def test_unmatched_hint_offers_places_still_ahead():
    q = _question(type="CLOSURE", activity_hint="박물관")
    assert q.candidates == tuple(a.id for a in ACTS)  # all end after 09:00


def test_a_picked_place_wins_over_the_words():
    assert _event(type="CLOSURE", activity_hint="시부야", activity_id="sky").activity_id == "sky"


def test_extend_needs_minutes():
    event = _event(type="EXTEND", activity_hint="하라주쿠", extra_minutes=30)
    assert (event.activity_id, event.extra_minutes) == ("harajuku", 30)
    assert _question(type="EXTEND", activity_hint="하라주쿠").field == "extra_minutes"


def test_extend_without_place_is_where_the_user_is():
    item = _item("harajuku", type="EXTEND", extra_minutes=30)
    assert item.event.activity_id == "harajuku" and item.assumed
    assert _question(type="EXTEND", extra_minutes=30).field == "activity_id"  # at the hotel


def test_wait_at_a_named_place():
    item = _item(type="WAIT", activity_hint="점심 식당", wait_minutes=40)
    assert (item.event.type, item.event.activity_id, item.event.minutes) == ("WAIT", "ramen", 40)
    assert item.chip == "이치란 대기 40분"


def test_reservation_change_parses_new_time():
    event = _event(type="RESERVATION_CHANGE", activity_hint="스카이", new_time="18:00")
    assert (event.activity_id, event.new_time) == ("sky", 18 * 60)


def test_reservation_shift_is_computed_from_the_booked_time():
    item = _item(type="RESERVATION_CHANGE", activity_hint="시부야 스카이", shift_minutes=-60)
    assert item.event.new_time == 1020 - 60
    assert item.chip == "시부야 스카이 예약 17:00 → 16:00"


def test_reservation_chip_does_not_say_booking_twice():
    acts = [*ACTS, _act("eiffel", "에펠탑 예약", start=1080, reservation_time=1080)]
    item = build_item(
        EventDraft(type="RESERVATION_CHANGE", activity_hint="에펠탑", shift_minutes=-30),
        now=NOW,
        location_id="hotel",
        activities=acts,
    )
    assert item.chip == "에펠탑 예약 18:00 → 17:30"


def test_reservation_without_time_asks_with_the_booked_time_prefilled():
    q = _question(type="RESERVATION_CHANGE", activity_hint="스카이")
    assert (q.kind, q.default) == ("time", 1020)


def test_reservation_without_place_offers_the_booked_pieces():
    q = _question(type="RESERVATION_CHANGE", shift_minutes=-60)
    assert q.candidates == ("sky", "izakaya")


def test_fatigue_needs_no_fields():
    assert _event(type="FATIGUE").type == EventType.FATIGUE


def test_must_visit_and_unknown_are_asked_not_guessed():
    assert _question(type="MUST_VISIT", activity_hint="도쿄타워").kind == "add_place"
    assert _question(type="UNKNOWN").kind == "type"


def test_questions_never_show_field_names():
    drafts = [
        {"type": "DELAY", "delay_minutes": 0},
        {"type": "WEATHER", "time_from": "x"},
        {"type": "CLOSURE"},
        {"type": "EXTEND"},
        {"type": "WAIT"},
        {"type": "RESERVATION_CHANGE"},
        {"type": "MUST_VISIT"},
        {"type": "UNKNOWN"},
    ]
    for d in drafts:
        text = _item(**d).question.text
        assert not any(c.isascii() and (c.isalpha() or c == "_") for c in text), text


def test_built_events_keep_one_per_place_and_stack_rain():
    items = [
        _item(type="WEATHER", time_from="10:00", time_to="11:00"),
        _item(type="WEATHER", time_from="15:00"),
        _item(type="CLOSURE", activity_hint="이자카야"),
        _item(type="CLOSURE", activity_hint="이자카야"),
        _item(type="FATIGUE"),
        _item(type="FATIGUE"),
    ]
    assert [e.type for e in built_events(items)] == ["WEATHER", "WEATHER", "CLOSURE", "FATIGUE"]


def test_same_input_gives_same_item():
    assert _item(type="DELAY", delay_minutes=45) == _item(type="DELAY", delay_minutes=45)
