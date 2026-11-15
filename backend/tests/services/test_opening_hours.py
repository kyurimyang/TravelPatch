from datetime import date

from app.services.opening_hours import UNKNOWN, DayHours, hours_for_weekday
from app.services.places_client import OpeningPeriod

MON = date(2026, 11, 16).weekday()  # Monday
FRI = date(2026, 11, 20).weekday()
SAT = date(2026, 11, 21).weekday()


def _p(open_day, open_min, close_day=None, close_min=None) -> OpeningPeriod:
    return OpeningPeriod(
        open_day=open_day, open_minute=open_min, close_day=close_day, close_minute=close_min
    )


def test_no_data_is_unknown_not_always_open():
    assert hours_for_weekday(None, MON) == UNKNOWN


def test_one_window_on_that_weekday():
    periods = (_p(1, 540, 1, 1080),)  # Google day 1 = Monday, 09:00-18:00
    assert hours_for_weekday(periods, MON) == DayHours("known", 540, 1080)


def test_weekday_without_a_period_is_closed():
    assert hours_for_weekday((_p(1, 540, 1, 1080),), SAT) == DayHours("closed")


def test_open_around_the_clock():
    assert hours_for_weekday((_p(0, 0),), MON) == DayHours("known", 0, 1440)


def test_lunch_break_is_not_flattened_into_one_window():
    periods = (_p(1, 660, 1, 840), _p(1, 1020, 1, 1320))
    assert hours_for_weekday(periods, MON) == UNKNOWN


def test_overnight_close_is_capped_at_midnight_for_the_opening_day():
    periods = (_p(5, 1080, 6, 120),)  # Friday 18:00 -> Saturday 02:00
    assert hours_for_weekday(periods, FRI) == DayHours("known", 1080, 1440)


def test_morning_spill_of_an_overnight_period_is_its_own_window():
    periods = (_p(5, 1080, 6, 120),)
    assert hours_for_weekday(periods, SAT) == DayHours("known", 0, 120)


def test_overnight_place_open_both_nights_is_unknown_on_the_second_day():
    periods = (_p(5, 1080, 6, 120), _p(6, 1080, 0, 120))
    assert hours_for_weekday(periods, SAT) == UNKNOWN
