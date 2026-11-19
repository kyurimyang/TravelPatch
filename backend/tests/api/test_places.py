from fastapi.testclient import TestClient

from app.main import app
from app.routers.deps import get_places_client
from app.services.places_client import PlaceCandidate, PlaceDetails, PlacesError

HOTEL = PlaceDetails(place_id="hotel", lat=35.6896, lng=139.6922, time_zone=None, periods=None)


class FakePlaces:
    def __init__(
        self, answer: list[PlaceCandidate] | Exception, hotel: PlaceDetails | Exception = HOTEL
    ) -> None:
        self.answer = answer
        self.hotel = hotel
        self.queries: list[str] = []
        self.nears: list[tuple[float, float] | None] = []

    def search(
        self, query: str, language: str = "ko", near=None, radius_m: float = 0.0
    ) -> list[PlaceCandidate]:
        self.queries.append(query)
        self.nears.append(near)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer

    def details(self, place_id: str) -> PlaceDetails:
        if isinstance(self.hotel, Exception):
            raise self.hotel
        return self.hotel


def _get(
    params: dict, answer, hotel: PlaceDetails | Exception = HOTEL
) -> tuple[object, FakePlaces]:
    fake = FakePlaces(answer, hotel)
    app.dependency_overrides[get_places_client] = lambda: fake
    try:
        return TestClient(app).get("/places/search", params=params), fake
    finally:
        app.dependency_overrides.clear()


SKY = PlaceCandidate(
    place_id="p1", name="시부야 스카이", address="도쿄 시부야구", lat=35.6, lng=139.7
)
YOKOCHO = PlaceCandidate(place_id="p2", name="시부야 요코초", address=None, lat=35.66, lng=139.70)


def test_search_returns_candidates_in_google_order_without_coordinates():
    res, _ = _get({"q": "시부야"}, [SKY, YOKOCHO])
    assert res.status_code == 200
    body = res.json()
    assert [c["place_id"] for c in body["candidates"]] == ["p1", "p2"]
    assert body["candidates"][0] == {
        "place_id": "p1",
        "name": "시부야 스카이",
        "address": "도쿄 시부야구",
        "far": None,  # no hotel given: distance unknown, not "near"
    }
    # Coordinates stay on the server: the browser keeps the trip for longer than 30 days.
    assert "lat" not in body["candidates"][0]


def test_city_narrows_the_query():
    _, fake = _get({"q": "스카이", "city": "도쿄"}, [])
    assert fake.queries == ["스카이 도쿄"]


def test_no_city_sends_the_query_as_typed():
    _, fake = _get({"q": "  Shibuya Sky  "}, [])
    assert fake.queries == ["Shibuya Sky"]


def test_no_hit_is_an_empty_list_not_an_error():
    res, _ = _get({"q": "없는장소"}, [])
    assert res.status_code == 200
    assert res.json()["candidates"] == []


def test_blank_query_is_rejected_before_google():
    res, fake = _get({"q": "   "}, [])
    assert res.status_code == 422
    assert fake.queries == []


# Shinjuku hotel; Shibuya is ~5 km away, Kamakura ~45 km.
KAMAKURA = PlaceCandidate(
    place_id="p3", name="가마쿠라 이치란", address=None, lat=35.319, lng=139.550
)


def test_near_biases_the_search_around_the_hotel():
    _, fake = _get({"q": "이치란", "near": "hotel"}, [])
    assert fake.nears == [(HOTEL.lat, HOTEL.lng)]


def test_without_near_there_is_no_bias():
    _, fake = _get({"q": "이치란"}, [])
    assert fake.nears == [None]


def test_candidates_far_from_the_hotel_are_flagged():
    res, _ = _get({"q": "이치란", "near": "hotel"}, [YOKOCHO, KAMAKURA])
    assert [c["far"] for c in res.json()["candidates"]] == [False, True]


def test_hotel_lookup_failure_still_searches_without_bias():
    res, fake = _get({"q": "이치란", "near": "hotel"}, [YOKOCHO], hotel=PlacesError("HTTP 404"))
    assert res.status_code == 200
    assert fake.nears == [None]
    assert res.json()["candidates"][0]["far"] is None


def test_google_failure_is_a_bad_gateway():
    res, _ = _get({"q": "시부야"}, PlacesError("Places returned HTTP 429: quota"))
    assert res.status_code == 502
