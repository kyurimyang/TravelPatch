"""Real Google calls. Run with: pytest -m live tests/services/test_live_places.py"""

import pytest

from app.services.places_client import GooglePlacesClient

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def client():
    return GooglePlacesClient()


def test_search_returns_candidates_with_ids_and_coordinates(client):
    found = client.search("Shibuya Sky Tokyo")
    assert found, "expected at least one candidate"
    assert all(c.place_id and -90 <= c.lat <= 90 and -180 <= c.lng <= 180 for c in found)


def test_details_for_a_searched_place(client):
    place_id = client.search("Shibuya Sky Tokyo")[0].place_id
    details = client.details(place_id)
    assert details.place_id == place_id
    assert details.time_zone == "Asia/Tokyo"
