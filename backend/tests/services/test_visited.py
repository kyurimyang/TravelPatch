"""Limit 8 (2026-11-22): places already visited are taken out on the server, before the engine.

Moved from frontend/src/lib/recovery.ts (forEngine / withoutVisited, A1-A2 of 2026-11-19) so
the eval, the API and the app share one rule. Scenario A: meiji 09:20-10:20, harajuku
10:30-11:30, omotesando 11:40-12:40, ramen 12:50-13:50, ...
"""

import pytest

from app.engine.recover import recover
from app.schemas.models import START_ID
from app.services.visited import VisitedError, apply_visited
from tests.engine.helpers import load_scenario_a, load_scenario_c

NOON = 12 * 60


def _at(location: str, now: int = NOON, kind: str = "WEATHER"):
    inp = load_scenario_a()
    if kind == "WEATHER":
        ev = {"type": "WEATHER", "occurred_at": now, "start_time": now, "location_id": location}
    else:
        ev = {"type": "DELAY", "occurred_at": now, "start_time": now, "location_id": location}
    return type(inp).model_validate({**inp.model_dump(mode="json"), "event": ev})


def _minutes(inp, a: str, b: str) -> int | None:
    return next((t.minutes for t in inp.travel if {t.a, t.b} == {a, b}), None)


def test_nothing_visited_leaves_the_input_alone() -> None:
    inp = _at("omotesando")
    assert apply_visited(inp, ()) == inp


def test_visited_places_leave_activities_preferences_and_travel() -> None:
    out = apply_visited(_at("omotesando"), ("meiji", "harajuku"))
    ids = [a.id for a in out.activities]
    assert ids == ["omotesando", "ramen", "shibuya_shop", "cafe", "sky", "izakaya"]
    assert {p.activity_id for p in out.preferences} == set(ids)
    assert not any({"meiji", "harajuku"} & {t.a, t.b} for t in out.travel)
    assert len(out.travel) == 21  # 6 activities + hotel: the engine wants a complete table


def test_a_visited_current_place_becomes_the_start_node() -> None:
    inp = _at("harajuku", NOON + 8, kind="DELAY")
    harajuku = next(a for a in inp.activities if a.id == "harajuku")
    out = apply_visited(inp, ("meiji", "harajuku"))
    assert out.event.location_id == START_ID
    assert (out.day.start_lat, out.day.start_lng) == (harajuku.lat, harajuku.lng)
    assert _minutes(out, START_ID, "omotesando") == _minutes(inp, "harajuku", "omotesando")
    assert _minutes(out, START_ID, "hotel") == _minutes(inp, "harajuku", "hotel")
    assert len(out.travel) == 28  # 6 activities + hotel + start


def test_an_unticked_current_place_stays_under_way() -> None:
    inp = _at("harajuku", NOON + 8, kind="DELAY")
    out = apply_visited(inp, ("meiji",))
    assert out.event == inp.event
    assert "harajuku" in {a.id for a in out.activities}
    assert out.day.start_lat is None


def test_an_arrival_airport_start_is_replaced() -> None:
    inp = _at("harajuku", NOON + 8, kind="DELAY")
    nodes = ["hotel", *(a.id for a in inp.activities)]
    data = inp.model_dump(mode="json")
    data["day"] |= {"start_lat": 35.55, "start_lng": 139.78}
    data["travel"] += [{"a": START_ID, "b": n, "minutes": 99} for n in nodes]
    out = apply_visited(type(inp).model_validate(data), ("meiji", "harajuku"))
    assert not any(t.minutes == 99 for t in out.travel)
    assert len(out.travel) == 28


def test_substitutes_for_a_visited_place_go_too() -> None:
    inp = load_scenario_c()  # izakaya_near / izakaya_far replace the izakaya
    data = inp.model_dump(mode="json")
    data["event"] = {"type": "WEATHER", "occurred_at": 1300, "start_time": 1300, "location_id": "hotel"}
    out = apply_visited(type(inp).model_validate(data), ("izakaya",))
    assert out.substitutes == ()
    assert not any("izakaya" in (t.a + t.b) for t in out.travel)


@pytest.mark.parametrize("bad", [("nowhere",), ("ramen",)])
def test_unknown_ids_and_the_event_target_cannot_be_visited(bad: tuple[str, ...]) -> None:
    inp = load_scenario_a()
    data = inp.model_dump(mode="json")
    data["event"] = {"type": "CLOSURE", "occurred_at": NOON, "location_id": "omotesando", "activity_id": "ramen"}
    with pytest.raises(VisitedError):
        apply_visited(type(inp).model_validate(data), bad)


def test_noon_recovery_with_the_morning_left_in_has_no_plan() -> None:
    # The A1 regression (rain at noon, at omotesando): meiji is must and its time has passed.
    inp = _at("omotesando")
    assert recover(inp) == []
    results = recover(apply_visited(inp, ("meiji", "harajuku")))
    assert results and all(r.violations == 0 for r in results)


def test_late_at_harajuku_without_visited_sends_the_traveller_back_to_meiji() -> None:
    # The other face of the same bug: a plan exists, but it re-plans the visited must (meiji)
    # for the afternoon. With the morning out, nothing visited comes back and more is kept.
    inp = _at("harajuku", NOON + 8, kind="DELAY")
    wrong = recover(inp)[0]
    assert next(c for c in wrong.changes if c.activity_id == "meiji").after is not None
    right = recover(apply_visited(inp, ("meiji", "harajuku")))[0]
    assert "meiji" not in {c.activity_id for c in right.changes}
    assert right.preservation_rate > wrong.preservation_rate
