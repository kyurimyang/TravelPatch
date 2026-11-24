import pytest

from app.main import app
from app.routers.deps import (
    get_guest_quota,
    get_places_client,
    get_places_client_optional,
    get_provider,
    get_provider_optional,
    get_routes_client_optional,
)


class _NotInTests:
    """Stands in for the real OpenAI / Google client: any use fails the test loudly."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __getattr__(self, attr: str):
        raise AssertionError(f"{self.name}.{attr} reached in a test; override the dependency")


@pytest.fixture(autouse=True)
def no_live_services():
    """API tests never reach OpenAI or Google by accident, and never depend on whether .env has
    keys (review 2026-11-19, A7: a missing key turned a 422 into a 503, since FastAPI resolves
    dependencies before it validates the body). Tests that need a client override these."""
    app.dependency_overrides[get_provider] = lambda: _NotInTests("LLM provider")
    app.dependency_overrides[get_places_client] = lambda: _NotInTests("Places client")
    app.dependency_overrides[get_provider_optional] = lambda: None
    app.dependency_overrides[get_places_client_optional] = lambda: None
    app.dependency_overrides[get_routes_client_optional] = lambda: None
    # Every test starts with an unused guest limit. Not an override: some tests clear the
    # overrides midway, and a counter shared across the run would make results depend on order.
    get_guest_quota.cache_clear()
    yield
    app.dependency_overrides.clear()
