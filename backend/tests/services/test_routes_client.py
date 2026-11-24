import json
from datetime import UTC, datetime

import httpx
import pytest

from app.schemas.enums import TravelMode
from app.services.routes_client import GoogleRoutesClient, RoutesConfigError, RoutesError

KEY = "test-key-123"
POINTS = {"a": (35.0, 139.0), "b": (35.1, 139.1), "c": (35.2, 139.2)}


def _client(handler) -> GoogleRoutesClient:
    return GoogleRoutesClient(
        api_key=KEY, client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def _el(o: int, d: int, seconds: int | None, condition: str = "ROUTE_EXISTS") -> dict:
    el: dict = {"originIndex": o, "destinationIndex": d, "condition": condition}
    if seconds is not None:
        el["duration"] = f"{seconds}s"
    return el


def test_missing_key_is_a_config_error(monkeypatch):
    monkeypatch.delenv("GOOGLE_ROUTES_API_KEY", raising=False)
    monkeypatch.setattr("app.services.routes_client.load_dotenv", lambda *_: None)
    with pytest.raises(RoutesConfigError):
        GoogleRoutesClient()


def test_sends_key_field_mask_mode_and_departure_time():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=[])

    when = datetime(2026, 12, 1, 9, 0, tzinfo=UTC)
    _client(handler).matrix(POINTS, TravelMode.TRANSIT, depart_at=when)
    assert seen["headers"]["x-goog-api-key"] == KEY
    assert "duration" in seen["headers"]["x-goog-fieldmask"]
    assert seen["body"]["travelMode"] == "TRANSIT"
    assert seen["body"]["departureTime"] == "2026-12-01T09:00:00+00:00"
    assert len(seen["body"]["origins"]) == 3 and len(seen["body"]["destinations"]) == 3


def test_car_is_sent_as_drive():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=[])

    _client(handler).matrix(POINTS, TravelMode.CAR)
    assert seen["body"]["travelMode"] == "DRIVE"
    assert "departureTime" not in seen["body"]


def test_keeps_the_longer_direction_rounded_up_to_5_minutes():
    # ids sorted: a=0, b=1, c=2.  a->b 7 min, b->a 11 min -> 11 -> 15.
    elements = [_el(0, 1, 7 * 60), _el(1, 0, 11 * 60), _el(0, 0, 0)]
    out = _client(lambda r: httpx.Response(200, json=elements)).matrix(POINTS, TravelMode.WALK)
    assert [(t.a, t.b, t.minutes, t.source) for t in out] == [("a", "b", 15, "api")]


def test_pairs_google_cannot_route_are_left_out():
    elements = [_el(0, 1, 600), _el(0, 2, None, "ROUTE_NOT_FOUND"), _el(1, 2, 300)]
    out = _client(lambda r: httpx.Response(200, json=elements)).matrix(POINTS, TravelMode.TRANSIT)
    assert [(t.a, t.b) for t in out] == [("a", "b"), ("b", "c")]


def test_transit_matrix_is_split_to_stay_under_100_elements():
    points = {f"p{i:02d}": (35.0 + i / 100, 139.0) for i in range(13)}  # 13 x 13 = 169 > 100
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=[])

    _client(handler).matrix(points, TravelMode.TRANSIT)
    assert len(bodies) == 2
    assert all(len(b["origins"]) * len(b["destinations"]) <= 100 for b in bodies)
    assert sum(len(b["origins"]) for b in bodies) == 13  # every origin asked exactly once


def test_http_error_raises_without_leaking_the_key():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json=[{"error": {"message": "API key not valid"}}])

    with pytest.raises(RoutesError) as exc:
        _client(handler).matrix(POINTS, TravelMode.WALK)
    assert "403" in str(exc.value) and KEY not in str(exc.value)


def test_network_failure_raises_routes_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom", request=request)

    with pytest.raises(RoutesError):
        _client(handler).matrix(POINTS, TravelMode.WALK)


# --- The on/off switch: real travel times stay off until ROUTES_TRAVEL_ENABLED is set ---


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, False),
        ("", False),
        ("0", False),
        ("false", False),
        ("1", True),
        ("true", True),
        (" TRUE ", True),
    ],
)
def test_routes_are_off_unless_explicitly_enabled(monkeypatch, value, expected):
    from app.services.routes_client import routes_enabled

    monkeypatch.setattr("app.services.routes_client.load_dotenv", lambda *_: None)
    if value is None:
        monkeypatch.delenv("ROUTES_TRAVEL_ENABLED", raising=False)
    else:
        monkeypatch.setenv("ROUTES_TRAVEL_ENABLED", value)
    assert routes_enabled() is expected


def test_the_dependency_gives_no_client_while_the_switch_is_off(monkeypatch):
    from app.routers import deps

    monkeypatch.setenv("GOOGLE_ROUTES_API_KEY", KEY)  # a key alone must not turn it on
    monkeypatch.delenv("ROUTES_TRAVEL_ENABLED", raising=False)
    monkeypatch.setattr("app.services.routes_client.load_dotenv", lambda *_: None)
    deps._google_routes.cache_clear()
    assert deps.get_routes_client_optional() is None
    monkeypatch.setenv("ROUTES_TRAVEL_ENABLED", "1")
    assert deps.get_routes_client_optional() is not None
    deps._google_routes.cache_clear()
