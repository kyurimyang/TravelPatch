"""Who may spend the LLM / Places budget (decisions 2026-11-22, 2026-11-23): guests up to a daily
limit per IP and in total, signed-in users up to their own (larger) limit, an untrusted token never."""

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


def _quota(llm: int = 1, places: int = 1, per_user: int = 50) -> GuestQuota:
    q = GuestQuota(
        {
            Kind.LLM: Limit(per_ip=llm, total=100, per_user=per_user),
            Kind.PLACES: Limit(per_ip=places, total=100, per_user=per_user),
        }
    )
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


def test_signed_in_user_has_a_limit_of_their_own() -> None:
    _quota(places=1, per_user=3)
    assert [_search({"Authorization": "Bearer good"}) for _ in range(3)] == [200, 200, 200]
    assert _search() == 200  # the guest's one call is still unused
    # Sign-up needs no e-mail check: signed in is not unlimited (2026-11-23).
    assert _search({"Authorization": "Bearer good"}) == 429


def test_vercel_ip_counts_each_guest_apart() -> None:
    _quota(places=1)
    a = {"X-Vercel-Proxied-For": "203.0.113.1", "CF-Connecting-IP": "3.36.69.146"}
    b = {"X-Vercel-Proxied-For": "203.0.113.2", "CF-Connecting-IP": "3.36.69.146"}
    assert [_search(a), _search(a), _search(b)] == [200, 429, 200]  # same Vercel egress, apart


def test_direct_call_counts_by_cloudflare_peer() -> None:
    _quota(places=1)
    assert _search({"CF-Connecting-IP": "203.0.113.9"}) == 200
    assert _search({"CF-Connecting-IP": "203.0.113.9"}) == 429


def test_forged_forwarded_for_does_not_make_a_new_guest() -> None:
    # Measured 2026-11-22: these two could be passed on as the caller sent them.
    _quota(places=1)
    real = {"X-Vercel-Proxied-For": "203.0.113.1"}
    assert _search(real) == 200
    forged = {**real, "X-Forwarded-For": "6.6.6.6", "X-Vercel-Forwarded-For": "9.9.9.9"}
    assert _search(forged) == 429


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


def test_recomputing_from_the_answer_does_not_search_again() -> None:
    # Since 2026-11-24 a plan that drops a piece searches a nearby place once (and is charged).
    # Sending the answer's used_input back (recompute) finds those substitutes in place.
    _with_substitute_services()
    q = _quota(llm=5, places=5)
    first = client.post("/recoveries", json=load_scenario_a().model_dump(mode="json")).json()
    spent = dict(q._count)
    for _ in range(3):
        assert client.post("/recoveries", json=first["used_input"]).status_code == 200
    assert dict(q._count) == spent
