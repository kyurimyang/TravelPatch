"""Rain or "실내 우선": indoor stand-ins for outdoor pieces (2026-11-26), and closures that come
as a second event."""

from app.llm.substitute_query import SubstituteQuery, substitute_query
from app.schemas.enums import Wish
from app.schemas.events import ClosureEvent, DelayEvent, WeatherEvent
from app.services.places_client import PlaceCandidate, PlaceDetails
from app.services.substitute_finder import (
    add_substitutes,
    build_substitutes,
    closed_targets,
    indoor_targets,
    place_outdoor,
    wants_substitutes,
)
from tests.engine.helpers import load_scenario_a

NOW = 540


def _day(*more, wishes=()):
    inp = load_scenario_a()
    data = inp.model_dump()
    data["event"] = DelayEvent(occurred_at=NOW, start_time=NOW).model_dump()
    data["more_events"] = [e.model_dump() for e in more]
    data["wishes"] = list(wishes)
    return type(inp).model_validate(data)


def test_google_types_decide_inside_or_outside_only_when_clear():
    assert place_outdoor(("museum", "point_of_interest")) is False
    assert place_outdoor(("ramen_restaurant",)) is False
    assert place_outdoor(("park", "tourist_attraction")) is True
    assert place_outdoor(("tourist_attraction",)) is None  # could be either
    assert place_outdoor(("park", "cafe")) is None  # a cafe in a park: not settled


def test_a_substitute_carries_what_google_says_about_it():
    target = next(a for a in load_scenario_a().activities if a.id == "harajuku")
    hit = PlaceCandidate(
        place_id="p", name="실내 전시", address=None, lat=0, lng=0, types=("museum",)
    )
    details = PlaceDetails(
        place_id="p", lat=35.673, lng=139.708, time_zone="Asia/Tokyo", periods=None
    )
    (sub,) = build_substitutes(target, [(hit, details)], None).substitutes
    assert sub.outdoor is False


def test_no_rain_and_no_wish_searches_nothing_indoors():
    assert indoor_targets(_day()) == []
    assert not wants_substitutes(_day())


def test_rain_searches_the_most_valuable_outdoor_pieces_first():
    rain = WeatherEvent(occurred_at=NOW, start_time=600)
    # meiji (must) before harajuku (nice); omotesando (optional) is past the cap of two.
    assert indoor_targets(_day(rain)) == ["meiji", "harajuku"]
    assert indoor_targets(_day(wishes=[Wish.INDOOR])) == ["meiji", "harajuku"]


def test_a_closure_in_more_events_is_searched_too():
    rain = WeatherEvent(occurred_at=NOW, start_time=600)
    closed = ClosureEvent(occurred_at=NOW, activity_id="cafe")
    assert closed_targets(_day(rain, closed)) == ["cafe"]


class _Provider:
    def __init__(self):
        self.users: list[str] = []

    def complete_json(self, *, system, user, schema):
        self.users.append(user)
        return SubstituteQuery(query=None)


def test_indoor_search_asks_for_an_inside_place():
    provider = _Provider()
    assert (
        substitute_query(provider, "메이지 신궁", "sightseeing", indoor=True) == "실내 메이지 신궁"
    )
    assert provider.users[-1].endswith("indoor: yes")
    assert substitute_query(provider, "카페", "cafe") == "카페"


class _Places:
    def __init__(self):
        self.queries: list[str] = []

    def search(self, query, near):
        self.queries.append(query)
        return []

    def details(self, place_id):
        raise AssertionError("no hits, no details")


def test_add_substitutes_searches_closed_and_outdoor_pieces():
    rain = WeatherEvent(occurred_at=NOW, start_time=600)
    closed = ClosureEvent(occurred_at=NOW, activity_id="cafe")
    places = _Places()
    inp = _day(rain, closed)
    assert add_substitutes(inp, _Provider(), places) is inp  # nothing found: unchanged
    assert sorted(places.queries) == sorted(
        ["카페", "실내 메이지 신궁", "실내 하라주쿠 다케시타 거리"]
    )


def test_walking_from_types_and_category():
    from app.schemas.enums import Category
    from app.services.place_kind import place_walking

    assert place_walking(("park",), Category.SIGHTSEEING) is True
    assert place_walking(("market",), Category.SHOPPING) is True
    assert place_walking(("museum",), Category.SIGHTSEEING) is None  # not settled
    assert place_walking(("park",), Category.CAFE) is False  # a cafe in a park: sitting down


def _hit_at(name: str, lat: float, lng: float, types: tuple[str, ...]):
    hit = PlaceCandidate(place_id=name, name=name, address=None, lat=lat, lng=lng, types=types)
    return hit, PlaceDetails(place_id=name, lat=lat, lng=lng, time_zone="Asia/Tokyo", periods=None)


def test_a_place_already_in_the_day_is_not_a_stand_in():
    day = load_scenario_a()
    meiji = next(a for a in day.activities if a.id == "meiji")
    harajuku = next(a for a in day.activities if a.id == "harajuku")
    places = [
        _hit_at("하라주쿠", harajuku.lat, harajuku.lng, ("tourist_attraction",)),  # in the day
        _hit_at("다른 곳", meiji.lat + 0.01, meiji.lng, ("museum",)),
    ]
    found = build_substitutes(meiji, places, None, [(harajuku.lat, harajuku.lng)])
    assert [s.title for s in found.substitutes] == ["다른 곳"]


def test_a_hotel_is_never_a_stand_in():
    meiji = next(a for a in load_scenario_a().activities if a.id == "meiji")
    places = [_hit_at("호텔", meiji.lat + 0.01, meiji.lng, ("lodging", "tourist_attraction"))]
    assert build_substitutes(meiji, places, None).substitutes == ()


def test_a_sight_is_not_stood_in_for_by_a_cafe():
    meiji = next(a for a in load_scenario_a().activities if a.id == "meiji")
    places = [
        _hit_at("카페", meiji.lat + 0.01, meiji.lng, ("cafe", "food")),
        _hit_at("미술관 카페", meiji.lat + 0.02, meiji.lng, ("art_gallery", "cafe")),
    ]
    found = build_substitutes(meiji, places, None)
    assert [s.title for s in found.substitutes] == ["미술관 카페"]  # its main kind is a gallery
