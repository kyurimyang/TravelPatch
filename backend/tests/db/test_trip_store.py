"""save_trip / load_trips on the dev Supabase project (migration 0003)."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from postgrest.exceptions import APIError

from tests.db.conftest import TEST_PLACE_PREFIX

pytestmark = pytest.mark.db


def place(name: str) -> str:
    return f"{TEST_PLACE_PREFIX}{name}"


def item(key: str, title: str, start: int | None, end: int | None, **extra: Any) -> dict[str, Any]:
    """An item in the browser's shape (frontend/src/store/trip.tsx), every field present."""
    return {
        "id": key,
        "title": title,
        "category": "sightseeing",
        "start": start,
        "end": end,
        "durationEstimated": False,
        "reservationTime": None,
        "note": None,
        "placeQuery": None,
        "placeId": place(key),
        "tier": "nice",
        "dropped": False,
        "patched": False,
        "substituted": False,
    } | extra


def sample_trip() -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "city": "도쿄",
        "startDate": "2026-10-08",
        "endDate": "2026-10-09",
        "hotel": {"title": "신주쿠 호텔", "placeId": place("hotel")},
        "travelMode": "transit",
        "endDeadline": 1320,
        "arrival": {"time": 600, "bufferMinutes": None,
                    "airport": {"title": "하네다", "placeId": place("hnd")}},
        "departure": {"time": 1140, "bufferMinutes": 150,
                      "airport": {"title": "나리타", "placeId": place("nrt")}},
        "days": [
            {
                "date": "2026-10-08",
                "label": "1일차",
                "issues": [],
                "items": [
                    item("d0-0", "오모테산도 산책", 660, 720, placeQuery="오모테산도"),
                    item("d0-1", "스카이 전망대", 1020, 1080, tier="must", reservationTime=1020),
                    item("d0-2", "이자카야", None, None, category="meal", placeId=None,
                         note="시간 미정", durationEstimated=True),
                ],
            },
            {"date": "2026-10-09", "label": None, "issues": [], "items": []},
        ],
        "patches": [
            {
                "id": "patch-1",
                "date": "2026-10-08",
                "savedAt": "2026-10-08T03:10:00.000Z",
                "strategy": "balanced",
                "preservationRate": 0.9,
                "chips": ["2시간 늦음"],
                "eventType": "DELAY",
                "changes": [
                    {"itemId": "d0-1", "op": "keep", "before": None, "after": None},
                    {"itemId": "d0-0", "op": "drop",
                     "before": {"start": 660, "end": 720}, "after": None},
                    {"itemId": "d0-2", "op": "shrink",
                     "before": {"start": 1170, "end": 1260}, "after": {"start": 1170, "end": 1230}},
                ],
            }
        ],
    }


def comparable(trip: dict[str, Any]) -> dict[str, Any]:
    """A trip without what the server adds (revision) and with timestamps as instants, so
    "…000Z" and "…+00:00" compare equal."""
    out = {k: v for k, v in trip.items() if k != "revision"}
    out["patches"] = [
        p | {"savedAt": datetime.fromisoformat(p["savedAt"].replace("Z", "+00:00"))}
        for p in trip["patches"]
    ]
    return out


def save(client, trip: dict[str, Any], base: int | None) -> int:
    return client.rpc("save_trip", {"trip": trip, "base_revision": base}).execute().data


def load(client) -> list[dict[str, Any]]:
    return client.rpc("load_trips", {}).execute().data


def test_round_trip_keeps_the_trip_as_the_browser_has_it(make_user):
    _, alice = make_user()
    trip = sample_trip()

    assert save(alice, trip, None) == 1
    [loaded] = load(alice)

    assert loaded["revision"] == 1
    assert comparable(loaded) == comparable(trip)


def error_code(call) -> str:
    """The SQLSTATE of the error a call raises (the app tells failures apart by it)."""
    with pytest.raises(APIError) as caught:
        call()
    return caught.value.code


# --- revision: one device never silently overwrites another (decision 2026-11-19) -------------


def test_a_save_from_an_older_revision_is_refused(make_user):
    _, alice = make_user()
    trip = sample_trip()
    assert save(alice, trip, None) == 1
    assert save(alice, trip, 1) == 2  # device A saves on top of what it loaded

    # device B still holds revision 1
    assert error_code(lambda: save(alice, trip | {"city": "오사카"}, 1)) == "PT409"
    [loaded] = load(alice)
    assert (loaded["revision"], loaded["city"]) == (2, "도쿄")


def test_saving_a_new_trip_twice_is_refused_the_second_time(make_user):
    _, alice = make_user()
    trip = sample_trip()
    assert save(alice, trip, None) == 1
    assert error_code(lambda: save(alice, trip, None)) == "PT409"


def test_saving_a_trip_deleted_on_another_device_says_it_is_gone(make_user):
    _, alice = make_user()
    trip = sample_trip()
    save(alice, trip, None)
    alice.table("trips").delete().eq("id", trip["id"]).execute()

    assert error_code(lambda: save(alice, trip, 1)) == "PT410"


def test_a_trip_far_bigger_than_the_app_makes_is_refused(make_user):
    _, alice = make_user()
    trip = sample_trip()
    trip["days"] = [{"date": "2026-10-08", "label": None, "issues": [], "items": []}] * 61
    assert error_code(lambda: save(alice, trip, None)) == "22023"


# --- ownership: RLS and the checks inside save_trip --------------------------------------------


def test_another_user_can_neither_see_nor_overwrite_a_trip(make_user):
    _, alice = make_user()
    _, bob = make_user()
    trip = sample_trip()
    save(alice, trip, None)

    assert load(bob) == []
    assert bob.table("trips").select("id").execute().data == []
    assert bob.table("days").select("id").execute().data == []
    assert error_code(lambda: save(bob, trip | {"city": "오사카"}, 1)) == "42501"
    bob.table("trips").delete().eq("id", trip["id"]).execute()  # RLS: deletes nothing

    [loaded] = load(alice)
    assert (loaded["revision"], loaded["city"]) == (1, "도쿄")


def test_a_visitor_who_is_not_signed_in_cannot_call_the_functions(anon):
    # revoked from anon: refused before the function body runs
    assert error_code(lambda: save(anon, sample_trip(), None)) == "42501"
    assert error_code(lambda: load(anon)) == "42501"
    assert anon.table("trips").select("id").execute().data == []


# --- consents: a history the app can add to but not change --------------------------------------


def consent(user_id: str, **extra: Any) -> dict[str, Any]:
    return {"user_id": user_id, "terms_version": "2026-11-18",
            "age14": True, "terms": True, "privacy": True} | extra


def test_consents_are_added_with_the_servers_clock(make_user):
    alice_id, alice = make_user()
    before = datetime.now(UTC)
    alice.table("consents").insert(consent(alice_id)).execute()

    [row] = alice.table("consents").select("*").execute().data
    agreed = datetime.fromisoformat(row["agreed_at"])
    assert abs((agreed - before).total_seconds()) < 60  # stamped by now(), not by the app


def test_the_app_cannot_choose_when_a_consent_was_given(make_user):
    alice_id, alice = make_user()
    backdated = consent(alice_id, agreed_at="2020-01-01T00:00:00Z")
    assert error_code(lambda: alice.table("consents").insert(backdated).execute()) == "42501"


def test_a_consent_needs_all_three_checks(make_user):
    alice_id, alice = make_user()
    partial = consent(alice_id, privacy=False)
    assert error_code(lambda: alice.table("consents").insert(partial).execute()) == "23514"


def test_nobody_can_record_a_consent_for_someone_else(make_user):
    _, alice = make_user()
    bob_id, _ = make_user()
    assert error_code(lambda: alice.table("consents").insert(consent(bob_id)).execute()) == "42501"


def test_consents_cannot_be_changed_or_deleted_from_the_app(make_user):
    alice_id, alice = make_user()
    alice.table("consents").insert(consent(alice_id)).execute()

    # no update or delete policy: RLS lets these through as no-ops, so check the row afterwards
    try:
        alice.table("consents").update({"terms_version": "forged"}).eq("user_id", alice_id).execute()
    except APIError:
        pass  # a refusal is fine too
    alice.table("consents").delete().eq("user_id", alice_id).execute()

    rows = alice.table("consents").select("terms_version").execute().data
    assert rows == [{"terms_version": "2026-11-18"}]
