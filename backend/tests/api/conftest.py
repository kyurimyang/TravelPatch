import pytest

from app.main import app
from app.routers.deps import get_places_client_optional, get_provider_optional


@pytest.fixture(autouse=True)
def no_live_substitute_search():
    """API tests never reach OpenAI or Google by accident: substitute search is off unless a
    test overrides these itself."""
    app.dependency_overrides[get_provider_optional] = lambda: None
    app.dependency_overrides[get_places_client_optional] = lambda: None
    yield
    app.dependency_overrides.clear()
