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
    return GooglePlacesClient(api_key=KEY, client=httpx.Client(transport=httpx.MockTransport(handler)))


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
    assert [(c.place_id, c.name, c.lat, c.lng) for c in found] == [("p1", "시부야 스카이", 35.6, 139.7)]
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
