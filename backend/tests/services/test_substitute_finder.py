import json
from datetime import date
from pathlib import Path

from app.engine.recover import recover
from app.llm.substitute_query import SubstituteQuery
from app.schemas.enums import Op
from app.schemas.recovery import RecoveryInput
from app.services.places_client import OpeningPeriod, PlaceCandidate, PlaceDetails, PlacesError
from app.services.substitute_finder import add_substitutes, build_substitutes, needs_check_ids

SCENARIOS = Path(__file__).parents[1] / "scenarios"
TUESDAY = date(2026, 10, 6)  # weekday() == 1; Google counts it as day 2


def _closed_izakaya(day: date | None = TUESDAY) -> RecoveryInput:
    """Scenario C (izakaya closed) without its hand-made substitutes."""
    raw = json.loads((SCENARIOS / "scenario_c.json").read_text(encoding="utf-8"))
    raw.pop("expected", None)
    raw["substitutes"] = []
    raw["travel"] = [
        t for t in raw["travel"] if not {t["a"], t["b"]} & {"izakaya_near", "izakaya_far"}
    ]
    raw["day"]["date"] = day.isoformat() if day else None
    return RecoveryInput.model_validate(raw)


def _izakaya(inp: RecoveryInput):
    return next(a for a in inp.activities if a.id == "izakaya")


def _details(place_id: str, lat: float, lng: float, hours: tuple[int, int] | None) -> PlaceDetails:
    periods = None
    if hours is not None:  # open every day of the week in this window
        periods = tuple(
            OpeningPeriod(open_day=d, open_minute=hours[0], close_day=d, close_minute=hours[1])
            for d in range(7)
        )
    return PlaceDetails(
        place_id=place_id, lat=lat, lng=lng, time_zone="Asia/Tokyo", periods=periods
    )


def _closed_on_tuesday(place_id: str, lat: float, lng: float) -> PlaceDetails:
    periods = tuple(
        OpeningPeriod(open_day=d, open_minute=1020, close_day=d, close_minute=1380)
        for d in range(7)
        if d != 2
    )
    return PlaceDetails(
        place_id=place_id, lat=lat, lng=lng, time_zone="Asia/Tokyo", periods=periods
    )


# ---- build_substitutes (pure) ----


def _hit(name: str, types: tuple[str, ...] = ("japanese_izakaya_restaurant", "restaurant")):
    return PlaceCandidate(place_id=name, name=name, address=None, lat=0.0, lng=0.0, types=types)


def test_open_places_become_substitutes_in_google_order():
    target = _izakaya(_closed_izakaya())
    found = build_substitutes(
        target,
        [
            (_hit("가까운 이자카야"), _details("p1", target.lat + 0.002, target.lng, (1020, 1380))),
            (_hit("먼 이자카야"), _details("p2", target.lat + 0.02, target.lng, (1020, 1380))),
        ],
        TUESDAY.weekday(),
    )
    assert [(s.id, s.title, s.open_at, s.close_at) for s in found.substitutes] == [
        ("sub_izakaya_1", "가까운 이자카야", 1020, 1380),
        ("sub_izakaya_2", "먼 이자카야", 1020, 1380),
    ]
    near, far = found.substitutes
    assert near.replaces == "izakaya" and near.duration == target.ideal_duration
    assert near.penalty < far.penalty  # farther from the closed place, bigger penalty
    assert found.unknown_hours == frozenset()


def test_the_closed_place_itself_and_places_closed_that_day_are_left_out():
    target = _izakaya(_closed_izakaya())
    found = build_substitutes(
        target,
        [
            (_hit("원래 가게"), _details("p0", target.lat, target.lng, (1020, 1380))),
            (_hit("화요일 휴무"), _closed_on_tuesday("p1", target.lat + 0.002, target.lng)),
            (_hit("열린 곳"), _details("p2", target.lat + 0.003, target.lng, (1020, 1380))),
        ],
        TUESDAY.weekday(),
    )
    assert [s.title for s in found.substitutes] == ["열린 곳"]


def test_unknown_hours_are_kept_but_flagged():
    target = _izakaya(_closed_izakaya())
    found = build_substitutes(
        target,
        [(_hit("영업시간 모름"), _details("p1", target.lat + 0.002, target.lng, None))],
        TUESDAY.weekday(),
    )
    (sub,) = found.substitutes
    assert sub.open_at is None and sub.close_at is None
    assert found.unknown_hours == frozenset({"sub_izakaya_1"})


def test_no_date_means_hours_are_unknown():
    target = _izakaya(_closed_izakaya(day=None))
    found = build_substitutes(
        target,
        [(_hit("어딘가"), _details("p1", target.lat + 0.002, target.lng, (1020, 1380)))],
        None,
    )
    assert found.unknown_hours == frozenset({"sub_izakaya_1"})


# ---- add_substitutes (with fake LLM and Places) ----


class FakeLLM:
    def complete_json(self, *, system, user, schema):
        return SubstituteQuery(query="이자카야")


class FakePlaces:
    def __init__(self, details: dict[str, PlaceDetails], fail: bool = False) -> None:
        self._details = details
        self.fail = fail
        self.searches: list[tuple[str, tuple[float, float] | None]] = []

    def search(self, query, language="ko", near=None, radius_m=1500.0):
        self.searches.append((query, near))
        if self.fail:
            raise PlacesError("down")
        return [
            PlaceCandidate(place_id=pid, name=f"가게 {pid}", address=None, lat=d.lat, lng=d.lng)
            for pid, d in self._details.items()
        ]

    def details(self, place_id):
        return self._details[place_id]


def test_closure_gets_substitutes_and_the_engine_uses_one():
    inp = _closed_izakaya()
    target = _izakaya(inp)
    assert recover(inp) == []  # without substitutes there is no plan

    places = FakePlaces({"p1": _details("p1", target.lat + 0.003, target.lng, (1020, 1380))})
    with_subs = add_substitutes(inp, FakeLLM(), places)

    assert places.searches == [("이자카야", (target.lat, target.lng))]
    assert [s.id for s in with_subs.substitutes] == ["sub_izakaya_1"]
    assert needs_check_ids(with_subs) == frozenset()
    results = recover(with_subs)
    assert results, "a substitute should make a plan possible"
    change = next(c for c in results[0].changes if c.activity_id == "izakaya")
    assert change.op == Op.SUBSTITUTE and change.substitute_id == "sub_izakaya_1"


def test_places_failure_leaves_the_input_unchanged():
    inp = _closed_izakaya()
    out = add_substitutes(inp, FakeLLM(), FakePlaces({}, fail=True))
    assert out == inp


def test_given_substitutes_are_not_searched_again():
    raw = json.loads((SCENARIOS / "scenario_c.json").read_text(encoding="utf-8"))
    raw.pop("expected", None)
    inp = RecoveryInput.model_validate(raw)
    places = FakePlaces({})
    out = add_substitutes(inp, FakeLLM(), places)
    assert out == inp and places.searches == []


def test_substitute_with_unknown_hours_needs_check():
    inp = _closed_izakaya()
    target = _izakaya(inp)
    places = FakePlaces({"p1": _details("p1", target.lat + 0.003, target.lng, None)})
    assert needs_check_ids(add_substitutes(inp, FakeLLM(), places)) == frozenset({"sub_izakaya_1"})


def test_a_shop_is_not_a_substitute_for_a_meal():
    target = _izakaya(_closed_izakaya())
    found = build_substitutes(
        target,
        [
            (
                _hit("모자 가게", ("clothing_store", "store")),
                _details("p1", target.lat + 0.002, target.lng, (600, 1260)),
            ),
            (
                _hit("야키토리", ("yakitori_restaurant",)),
                _details("p2", target.lat + 0.003, target.lng, (1020, 1380)),
            ),
        ],
        TUESDAY.weekday(),
    )
    assert [s.title for s in found.substitutes] == ["야키토리"]


def test_late_night_hours_still_give_a_known_window():
    target = _izakaya(_closed_izakaya())
    late = PlaceDetails(
        place_id="p1",
        lat=target.lat + 0.002,
        lng=target.lng,
        time_zone="Asia/Tokyo",
        periods=tuple(
            OpeningPeriod(open_day=d, open_minute=1020, close_day=(d + 1) % 7, close_minute=120)
            for d in range(7)
        ),
    )
    (sub,) = build_substitutes(
        target, [(_hit("심야 이자카야"), late)], TUESDAY.weekday()
    ).substitutes
    assert (sub.open_at, sub.close_at) == (1020, 1440)
