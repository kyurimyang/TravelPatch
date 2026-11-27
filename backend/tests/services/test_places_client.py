import json

import httpx
import pytest

from app.services.places_client import (
    GooglePlacesClient,
    PlacesConfigError,
    PlacesError,
)

KEY = "test-key-123"


def _client(handler) -> GooglePlacesClient:
    return GooglePlacesClient(
        api_key=KEY, client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def test_missing_key_is_a_config_error(monkeypatch):
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    monkeypatch.setattr("app.services.places_client.load_dotenv", lambda *_: None)
    with pytest.raises(PlacesConfigError):
        GooglePlacesClient()


def test_search_sends_field_mask_and_key_and_parses_candidates():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "places": [
                    {
                        "id": "p1",
                        "displayName": {"text": "시부야 스카이"},
                        "formattedAddress": "Shibuya",
                        "location": {"latitude": 35.6, "longitude": 139.7},
                    },
                    {"displayName": {"text": "no id"}, "location": {"latitude": 1, "longitude": 2}},
                ]
            },
        )

    found = _client(handler).search("스카이")
    assert [(c.place_id, c.name, c.lat, c.lng) for c in found] == [
        ("p1", "시부야 스카이", 35.6, 139.7)
    ]
    assert seen["headers"]["x-goog-api-key"] == KEY
    assert "places.location" in seen["headers"]["x-goog-fieldmask"]
    assert seen["body"]["textQuery"] == "스카이" and seen["body"]["maxResultCount"] == 5


def test_search_with_no_results_returns_an_empty_list():
    assert _client(lambda r: httpx.Response(200, json={})).search("zzz") == []


def test_details_parses_location_timezone_and_periods():
    payload = {
        "id": "p1",
        "location": {"latitude": 35.6, "longitude": 139.7},
        "timeZone": {"id": "Asia/Tokyo"},
        "regularOpeningHours": {
            "periods": [
                {"open": {"day": 1, "hour": 9, "minute": 30}, "close": {"day": 1, "hour": 18}},
                {"open": {"day": 2, "hour": 0, "minute": 0}},
            ]
        },
    }
    details = _client(lambda r: httpx.Response(200, json=payload)).details("p1")
    assert (details.lat, details.lng, details.time_zone) == (35.6, 139.7, "Asia/Tokyo")
    first, second = details.periods
    assert (first.open_day, first.open_minute, first.close_minute) == (1, 570, 1080)
    assert second.close_day is None  # around the clock


def test_details_asks_for_and_reads_the_place_types():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["mask"] = request.headers.get("X-Goog-FieldMask", "")
        payload = {"id": "p1", "location": {"latitude": 1, "longitude": 2}, "types": ["park"]}
        return httpx.Response(200, json=payload)

    assert _client(handler).details("p1").types == ("park",)
    assert "types" in seen["mask"].split(",")


def test_details_without_hours_is_unknown_not_always_open():
    payload = {"id": "p1", "location": {"latitude": 1, "longitude": 2}}
    assert _client(lambda r: httpx.Response(200, json=payload)).details("p1").periods is None


def test_http_error_becomes_places_error_without_the_key():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"message": "API key not valid"}})

    with pytest.raises(PlacesError) as info:
        _client(handler).search("x")
    assert "403" in str(info.value) and KEY not in str(info.value)


def test_network_failure_becomes_places_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(PlacesError) as info:
        _client(handler).search("x")
    assert KEY not in str(info.value)


def test_search_near_a_point_sends_a_location_bias():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"places": []})

    _client(handler).search("이자카야", near=(35.66, 139.70))
    circle = seen["body"]["locationBias"]["circle"]
    assert circle["center"] == {"latitude": 35.66, "longitude": 139.70}
    assert circle["radius"] == 1500.0


def test_search_without_a_point_sends_no_bias():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"places": []})

    _client(handler).search("이자카야")
    assert "locationBias" not in seen["body"]


def test_search_with_hours_brings_the_details_in_one_request():
    """Substitutes (2026-11-27): hours, time zone and types come with the hits; no details call."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        place = {
            "id": "p1",
            "displayName": {"text": "헤이워드 갤러리"},
            "location": {"latitude": 51.506, "longitude": -0.116},
            "types": ["art_gallery", "museum"],
            "timeZone": {"id": "Europe/London"},
            "regularOpeningHours": {
                "periods": [
                    {"open": {"day": 3, "hour": 10, "minute": 0}, "close": {"day": 3, "hour": 18}}
                ]
            },
        }
        return httpx.Response(200, json={"places": [place, {"id": "no-location"}]})

    [(hit, d)] = _client(handler).search_with_hours("실내 미술관", near=(51.5, -0.1))
    assert len(seen) == 1 and seen[0].url.path.endswith("places:searchText")
    mask = seen[0].headers["X-Goog-FieldMask"]
    assert "places.regularOpeningHours.periods" in mask and "places.timeZone" in mask
    assert (hit.name, hit.types) == ("헤이워드 갤러리", ("art_gallery", "museum"))
    assert (d.place_id, d.time_zone, d.types) == ("p1", "Europe/London", ("art_gallery", "museum"))
    assert d.periods[0].open_day == 3 and d.periods[0].open_minute == 600


def test_the_plain_search_does_not_ask_for_hours():
    """Users picking a place: the cheaper mask, without the Enterprise fields."""
    seen = {}

    def handler(request):
        seen["mask"] = request.headers["X-Goog-FieldMask"]
        return httpx.Response(200, json={"places": []})

    _client(handler).search("시부야 스카이")
    assert "regularOpeningHours" not in seen["mask"]
