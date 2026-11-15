import pytest

from app.llm.disruption_interpreter import InterpretedDisruption
from app.schemas.enums import Category, EventType
from app.schemas.models import Activity
from app.services.event_builder import EventBuildError, build_event, match_activity

NOW = 9 * 60  # 09:00


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
    _act("meiji", "메이지 신궁"),
    _act("harajuku", "하라주쿠 다케시타 거리"),
    _act("omotesando", "오모테산도 산책"),
    _act("sky", "시부야 스카이"),
    _act("izakaya", "시부야 이자카야"),
]


def _interp(**fields) -> InterpretedDisruption:
    base = {
        "type": "UNKNOWN",
        "delay_minutes": None,
        "time_from": None,
        "time_to": None,
        "activity_hint": None,
        "extra_minutes": None,
        "new_time": None,
    }
    return InterpretedDisruption(**{**base, **fields})


def _build(**fields):
    return build_event(_interp(**fields), now=NOW, location_id="hotel", activities=ACTS)


def _code(**fields) -> EventBuildError:
    with pytest.raises(EventBuildError) as info:
        _build(**fields)
    return info.value


def test_delay_adds_minutes_to_now():
    event = _build(type="DELAY", delay_minutes=120)
    assert event.type == EventType.DELAY
    assert (event.occurred_at, event.start_time) == (NOW, NOW + 120)


def test_delay_past_midnight_is_refused():
    assert _code(type="DELAY", delay_minutes=24 * 60).code == "BAD_TIME"


def test_delay_without_minutes_asks_the_user():
    assert _code(type="DELAY").code == "MISSING_FIELD"


def test_weather_parses_clock_times():
    event = _build(type="WEATHER", time_from="12:00", time_to="15:30")
    assert (event.start_time, event.end_time) == (720, 930)


def test_weather_end_is_optional():
    assert _build(type="WEATHER", time_from="12:00").end_time is None


@pytest.mark.parametrize("bad", ["12시", "25:00", "12:60", "noon"])
def test_weather_rejects_bad_time_text(bad):
    assert _code(type="WEATHER", time_from=bad).code == "BAD_TIME"


def test_weather_end_must_be_after_start():
    assert _code(type="WEATHER", time_from="15:00", time_to="12:00").code == "BAD_TIME"


def test_closure_matches_activity_by_substring():
    assert _build(type="CLOSURE", activity_hint="이자카야").activity_id == "izakaya"


def test_match_ignores_spaces_and_case():
    assert match_activity("시부야스카이", ACTS).id == "sky"


def test_ambiguous_hint_lists_the_candidates():
    error = _code(type="CLOSURE", activity_hint="시부야")
    assert error.code == "AMBIGUOUS"
    assert set(error.candidates) == {"sky", "izakaya"}


def test_unmatched_hint_offers_every_activity():
    error = _code(type="CLOSURE", activity_hint="저녁 식당")
    assert error.code == "NO_MATCH"
    assert error.candidates == tuple(a.id for a in ACTS)


def test_extend_needs_activity_and_minutes():
    event = _build(type="EXTEND", activity_hint="하라주쿠", extra_minutes=30)
    assert (event.activity_id, event.extra_minutes) == ("harajuku", 30)
    assert _code(type="EXTEND", activity_hint="하라주쿠").code == "MISSING_FIELD"


def test_reservation_change_parses_new_time():
    event = _build(type="RESERVATION_CHANGE", activity_hint="스카이", new_time="18:00")
    assert (event.activity_id, event.new_time) == ("sky", 18 * 60)


def test_fatigue_needs_no_fields():
    assert _build(type="FATIGUE").type == EventType.FATIGUE


def test_must_visit_and_unknown_are_not_guessed():
    assert _code(type="MUST_VISIT", activity_hint="도쿄타워").code == "UNSUPPORTED"
    assert _code(type="UNKNOWN").code == "UNKNOWN_TYPE"


def test_same_input_gives_same_event():
    assert _build(type="DELAY", delay_minutes=45) == _build(type="DELAY", delay_minutes=45)
