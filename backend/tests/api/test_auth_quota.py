"""Who may spend the LLM / Places budget (decision 2026-11-22): signed-in users without a count,
guests up to a daily limit, an untrusted token never."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.deps import (
    get_guest_quota,
    get_places_client,
    get_places_client_optional,
    get_provider_optional,
    get_verifier_optional,
)
from app.services.auth import AuthError
from app.services.guest_quota import GuestQuota, Kind, Limit
from tests.api.test_places import SKY, FakePlaces
from tests.engine.helpers import load_scenario_a
from tests.services.test_substitute_finder import FakeLLM, _closed_izakaya, _details
from tests.services.test_substitute_finder import FakePlaces as FakeSubstitutePlaces

client = TestClient(app)


class FakeVerifier:
    def user_id(self, token: str) -> str:
        if token != "good":
            raise AuthError("InvalidSignatureError")
        return "user-1"


def _quota(llm: int = 1, places: int = 1) -> GuestQuota:
    q = GuestQuota({Kind.LLM: Limit(per_ip=llm, total=100), Kind.PLACES: Limit(per_ip=places, total=100)})
    app.dependency_overrides[get_guest_quota] = lambda: q
    return q


@pytest.fixture(autouse=True)
def fakes() -> None:
    app.dependency_overrides[get_places_client] = lambda: FakePlaces([SKY])
    app.dependency_overrides[get_verifier_optional] = lambda: FakeVerifier()


def _search(headers: dict[str, str] | None = None) -> int:
    return client.get("/places/search", params={"q": "skytree"}, headers=headers).status_code


def test_guest_is_refused_past_the_daily_limit() -> None:
    _quota(places=2)
    assert [_search() for _ in range(3)] == [200, 200, 429]


def test_signed_in_user_is_not_counted() -> None:
    _quota(places=1)
    assert [_search({"Authorization": "Bearer good"}) for _ in range(3)] == [200, 200, 200]
    assert _search() == 200  # the guest's one call is still unused


def test_forwarded_ip_counts_each_guest_apart() -> None:
    _quota(places=1)
    a = {"X-Forwarded-For": "203.0.113.1, 10.0.0.1"}  # user, then the proxy hop
    b = {"X-Forwarded-For": "203.0.113.2, 10.0.0.1"}
    assert [_search(a), _search(a), _search(b)] == [200, 429, 200]


@pytest.mark.parametrize("header", ["Bearer forged", "Basic good", "Bearer "])
def test_untrusted_authorization_is_401_not_a_guest(header: str) -> None:
    assert _search({"Authorization": header}) == 401


def test_token_without_supabase_settings_is_503() -> None:
    app.dependency_overrides[get_verifier_optional] = lambda: None
    assert _search({"Authorization": "Bearer good"}) == 503
    assert _search() == 200  # guests do not need the settings


def _with_substitute_services() -> None:
    inp = _closed_izakaya()
    target = next(a for a in inp.activities if a.id == "izakaya")
    places = FakeSubstitutePlaces({"p1": _details("p1", target.lat + 0.003, target.lng, None)})
    app.dependency_overrides[get_provider_optional] = lambda: FakeLLM()
    app.dependency_overrides[get_places_client_optional] = lambda: places


def test_guest_past_the_limit_still_gets_the_engine_without_a_search() -> None:
    _with_substitute_services()
    _quota(llm=0)
    body = client.post("/recoveries", json=_closed_izakaya().model_dump(mode="json")).json()
    # The same answer as a server without keys: solved, no searched substitute.
    assert [b["kind"] for b in body["blockers"]] == ["closed_no_substitute"]


def test_recovery_without_a_search_does_not_use_the_limit() -> None:
    _with_substitute_services()
    q = _quota(llm=1, places=1)
    for _ in range(3):  # recompute, lock, restore...: none of them search
        assert client.post("/recoveries", json=load_scenario_a().model_dump(mode="json")).status_code == 200
    assert q.charge(Kind.LLM, "testclient")  # still unused
