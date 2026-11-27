from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.engine.recover import recover
from app.schemas.enums import Category, Tier, TimeRigidity, TravelMode
from app.schemas.events import DelayEvent
from app.schemas.models import HOTEL_ID, START_ID, TravelTime
from app.schemas.plan import (
    ARRIVAL_BUFFER,
    DEPARTURE_BUFFER,
    Flight,
    PlanItem,
    PlanRequest,
)
from app.schemas.recovery import RecoveryInput
from app.services.places_client import OpeningPeriod, PlaceDetails, PlacesError
from app.services.plan_builder import build_plan, min_duration_for
from app.services.routes_client import RoutesError

FRIDAY = date(2026, 11, 20)  # Google day 5

COORDS = {
    "hotel": (35.6896, 139.7006),  # Shinjuku
    "meiji": (35.6764, 139.6993),
    "ramen": (35.6702, 139.7027),
    "sky": (35.6585, 139.7021),
}


def _every_day(open_minute: int, close_minute: int) -> tuple[OpeningPeriod, ...]:
    return tuple(
        OpeningPeriod(open_day=d, open_minute=open_minute, close_day=d, close_minute=close_minute)
        for d in range(7)
    )


class FakePlaces:
    def __init__(
        self,
        hours: dict[str, tuple[OpeningPeriod, ...] | None],
        fail: set[str] = frozenset(),
        types: dict[str, tuple[str, ...]] | None = None,
    ):
        self.hours = hours
        self.fail = fail
        self.types = types or {}
        self.asked: list[str] = []

    def details(self, place_id: str) -> PlaceDetails:
        self.asked.append(place_id)
        if place_id in self.fail:
            raise PlacesError("down")
        lat, lng = COORDS[place_id]
        return PlaceDetails(
            place_id=place_id,
            lat=lat,
            lng=lng,
            time_zone="Asia/Tokyo",
            periods=self.hours.get(place_id),
            types=self.types.get(place_id, ()),
        )


def _item(
    id: str, start: int, end: int, *, category=Category.SIGHTSEEING, tier=Tier.NICE, reserved=False
) -> PlanItem:
    return PlanItem(
        id=id,
        title=id,
        category=category,
        start=start,
        end=end,
        place_id=id,
        tier=tier,
        reservation_time=start if reserved else None,
    )


def _request(mode: TravelMode = TravelMode.TRANSIT) -> PlanRequest:
    return PlanRequest(
        date=FRIDAY,
        hotel_place_id="hotel",
        end_deadline=22 * 60,
        travel_mode=mode,
        items=(
            _item("meiji", 600, 690, tier=Tier.MUST),
            _item("ramen", 720, 780, category=Category.MEAL),
            _item("sky", 1020, 1110, tier=Tier.MUST, reserved=True),
        ),
    )


def _places() -> FakePlaces:
    return FakePlaces(
        {
            "meiji": _every_day(300, 1110),
            "ramen": _every_day(660, 1320),
            "sky": _every_day(600, 1380),
        }
    )


def test_builds_activities_with_coordinates_and_hours():
    plan = build_plan(_request(), _places())
    meiji = next(a for a in plan.activities if a.id == "meiji")
    assert (meiji.lat, meiji.lng) == COORDS["meiji"]
    assert (meiji.planned_start, meiji.planned_end) == (600, 690)
    assert (meiji.open_at, meiji.close_at) == (300, 1110)
    assert meiji.outdoor is None  # no types from Google: unknown, never guessed
    assert plan.warnings == ()


def test_google_types_say_outdoor_and_walking_or_nothing():
    places = _places()
    places.types = {
        "meiji": ("park", "tourist_attraction"),
        "ramen": ("ramen_restaurant", "restaurant"),
        "sky": ("tourist_attraction", "point_of_interest"),  # does not settle it
    }
    acts = {a.id: a for a in build_plan(_request(), places).activities}
    assert (acts["meiji"].outdoor, acts["meiji"].walking) == (True, True)
    assert (acts["ramen"].outdoor, acts["ramen"].walking) == (False, False)  # a meal: sitting
    assert (acts["sky"].outdoor, acts["sky"].walking) == (None, None)


def test_day_starts_at_the_hotel_in_time_for_the_first_item():
    plan = build_plan(_request(), _places())
    to_first = next(t.minutes for t in plan.travel if {t.a, t.b} == {HOTEL_ID, "meiji"})
    assert plan.day.start_time == 600 - to_first
    assert plan.day.end_deadline == 22 * 60
    assert plan.day.date == FRIDAY and plan.day.timezone == "Asia/Tokyo"
    assert (plan.day.end_lat, plan.day.end_lng) == COORDS["hotel"]


def test_preferences_follow_the_rules():
    plan = build_plan(_request(), _places())
    prefs = {p.activity_id: p for p in plan.preferences}
    assert prefs["meiji"].tier == Tier.MUST
    assert prefs["ramen"].substitutability == 0.6  # a meal can be eaten elsewhere
    assert prefs["meiji"].substitutability == 0.2
    assert prefs["sky"].time_rigidity == TimeRigidity.RESERVED
    assert prefs["ramen"].time_rigidity == TimeRigidity.FLEXIBLE
    sky = next(a for a in plan.activities if a.id == "sky")
    assert sky.reservation_time == 1020


@pytest.mark.parametrize(
    ("planned", "expected"), [(90, 45), (60, 30), (45, 20), (25, 15), (10, 10)]
)
def test_min_duration_is_half_rounded_down_to_5_but_at_least_15(planned, expected):
    assert min_duration_for(planned) == expected


def test_travel_table_covers_every_pair_with_the_chosen_mode():
    transit = build_plan(_request(), _places()).travel
    walk = build_plan(_request(TravelMode.WALK), _places()).travel
    assert len(transit) == 6  # hotel + 3 places = 4 points, 6 pairs
    far = lambda table: next(t.minutes for t in table if {t.a, t.b} == {HOTEL_ID, "sky"})
    assert far(walk) > far(transit)


def test_closed_that_day_is_a_warning_not_a_silent_fix():
    places = _places()
    places.hours["ramen"] = tuple(
        p for p in _every_day(660, 1320) if p.open_day != 5
    )  # closed Fridays
    plan = build_plan(_request(), places)
    assert [(w.code, w.activity_id) for w in plan.warnings] == [("CLOSED_THAT_DAY", "ramen")]


def test_each_place_is_looked_up_once():
    places = _places()
    build_plan(_request(), places)
    assert sorted(places.asked) == ["hotel", "meiji", "ramen", "sky"]


def test_google_failure_raises():
    with pytest.raises(PlacesError):
        build_plan(_request(), FakePlaces({}, fail={"ramen"}))


def test_the_built_plan_goes_straight_into_the_engine():
    plan = build_plan(_request(), _places())
    inp = RecoveryInput(
        day=plan.day,
        activities=plan.activities,
        preferences=plan.preferences,
        travel=plan.travel,
        event=DelayEvent(occurred_at=540, location_id=HOTEL_ID, start_time=660),
    )
    results = recover(inp)
    assert results and all(r.violations == 0 for r in results)


# --- flights (decision 2026-11-18): the arrival sets the start, the departure the deadline ---

COORDS["haneda"] = (35.5494, 139.7798)


def _flight_request(
    *, arrival: Flight | None = None, departure: Flight | None = None
) -> PlanRequest:
    return PlanRequest(
        date=FRIDAY,
        hotel_place_id="hotel",
        end_deadline=None if departure else 22 * 60,
        items=_request().items,
        arrival=arrival,
        departure=departure,
    )


def test_arrival_day_starts_at_the_airport_after_the_default_buffer():
    plan = build_plan(
        _flight_request(arrival=Flight(time=420, airport_place_id="haneda")), _places()
    )
    assert plan.day.start_time == 420 + ARRIVAL_BUFFER
    assert (plan.day.start_lat, plan.day.start_lng) == COORDS["haneda"]
    assert (plan.day.end_lat, plan.day.end_lng) == COORDS["hotel"]  # still ends at the hotel
    assert len(plan.travel) == 10  # start + hotel + 3 places = 5 points, 10 pairs


def test_departure_day_ends_at_the_airport_before_the_default_buffer():
    plan = build_plan(
        _flight_request(departure=Flight(time=23 * 60, airport_place_id="haneda")),
        _places(),
    )
    assert plan.day.end_deadline == 23 * 60 - DEPARTURE_BUFFER
    assert (plan.day.end_lat, plan.day.end_lng) == COORDS["haneda"]
    assert plan.day.start_lat is None  # the morning still starts at the hotel


def test_the_user_can_change_the_buffer():
    arrival = Flight(time=420, airport_place_id="haneda", buffer_minutes=30)
    departure = Flight(time=23 * 60, airport_place_id="haneda", buffer_minutes=120)
    plan = build_plan(_flight_request(arrival=arrival, departure=departure), _places())
    assert (plan.day.start_time, plan.day.end_deadline) == (450, 23 * 60 - 120)


def test_an_item_before_the_user_can_get_there_from_the_airport_is_a_warning():
    # Lands 9:00 + 60 min: meiji at 10:00 cannot be reached in time. Warned, not moved.
    plan = build_plan(
        _flight_request(arrival=Flight(time=540, airport_place_id="haneda")), _places()
    )
    assert ("BEFORE_ARRIVAL", "meiji") in [(w.code, w.activity_id) for w in plan.warnings]
    meiji = next(a for a in plan.activities if a.id == "meiji")
    assert meiji.planned_start == 600


def test_an_item_that_misses_the_flight_is_a_warning():
    # Take-off 20:00 - 180 = 17:00 at the airport: sky (17:00-18:30) cannot fit.
    plan = build_plan(
        _flight_request(departure=Flight(time=20 * 60, airport_place_id="haneda")),
        _places(),
    )
    assert ("AFTER_DEPARTURE", "sky") in [(w.code, w.activity_id) for w in plan.warnings]


def test_end_deadline_or_departure_but_not_both():
    with pytest.raises(ValidationError):
        PlanRequest(date=FRIDAY, hotel_place_id="hotel", items=_request().items)
    with pytest.raises(ValidationError):
        PlanRequest(
            date=FRIDAY,
            hotel_place_id="hotel",
            end_deadline=22 * 60,
            items=_request().items,
            departure=Flight(time=23 * 60, airport_place_id="haneda"),
        )


def test_buffers_must_leave_some_day():
    # Lands 20:00 + 60 = 21:00, but the flight out needs the airport by 21:00 (24:00 - 180).
    with pytest.raises(ValidationError, match="no time left"):
        _flight_request(
            arrival=Flight(time=20 * 60, airport_place_id="haneda"),
            departure=Flight(time=24 * 60, airport_place_id="haneda"),
        )


def test_arrival_day_goes_straight_into_the_engine_from_the_airport():
    plan = build_plan(
        _flight_request(arrival=Flight(time=420, airport_place_id="haneda")), _places()
    )
    inp = RecoveryInput(
        day=plan.day,
        activities=plan.activities,
        preferences=plan.preferences,
        travel=plan.travel,
        event=DelayEvent(occurred_at=600, location_id=START_ID, start_time=600),
    )
    results = recover(inp)
    assert results and all(r.violations == 0 for r in results)


# --- Real travel times from Google Routes (falls back to estimates) ---


class FakeRoutes:
    """Answers only the pairs it was given; records what it was asked."""

    def __init__(self, known: dict[tuple[str, str], int] | None = None, fail: bool = False):
        self.known = known or {}
        self.fail = fail
        self.calls: list[tuple[set[str], TravelMode, datetime | None]] = []

    def matrix(self, points, mode, depart_at=None):
        self.calls.append((set(points), mode, depart_at))
        if self.fail:
            raise RoutesError("down")
        return tuple(
            TravelTime(a=a, b=b, minutes=m, source="api") for (a, b), m in self.known.items()
        )


def test_routes_minutes_replace_estimates_and_the_rest_stay_estimates():
    routes = FakeRoutes({(HOTEL_ID, "meiji"): 25})
    table = build_plan(_request(), _places(), routes=routes).travel
    by_pair = {frozenset((t.a, t.b)): t for t in table}
    assert len(table) == 6
    assert by_pair[frozenset((HOTEL_ID, "meiji"))].source == "api"
    assert by_pair[frozenset((HOTEL_ID, "meiji"))].minutes == 25
    assert by_pair[frozenset((HOTEL_ID, "sky"))].source == "estimate"


def test_a_routes_failure_falls_back_to_estimates_without_failing_the_plan():
    table = build_plan(_request(), _places(), routes=FakeRoutes(fail=True)).travel
    assert len(table) == 6 and {t.source for t in table} == {"estimate"}


def test_no_routes_client_means_estimates_only():
    assert {t.source for t in build_plan(_request(), _places()).travel} == {"estimate"}


def test_routes_is_asked_for_all_points_with_mode_and_first_start_in_the_trip_zone():
    routes = FakeRoutes()
    now = datetime(2026, 11, 1, tzinfo=UTC)
    build_plan(_request(TravelMode.WALK), _places(), routes=routes, now=now)
    points, mode, depart_at = routes.calls[0]
    assert points == {HOTEL_ID, "meiji", "ramen", "sky"} and mode is TravelMode.WALK
    assert depart_at == datetime(2026, 11, 20, 10, 0, tzinfo=ZoneInfo("Asia/Tokyo"))


def test_a_departure_time_in_the_past_is_not_sent():
    routes = FakeRoutes()
    now = datetime(2026, 12, 1, tzinfo=UTC)  # after the trip day
    build_plan(_request(), _places(), routes=routes, now=now)
    assert routes.calls[0][2] is None
