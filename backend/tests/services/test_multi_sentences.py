"""Sentences with several things at once, with a fixed reading (tests/fixtures/multi_sentences.json):
the rules build every event and every candidate answers all of them (tests/services/multi_eval.py).
The same cases go through the real model in tests/llm/test_live_multi_sentences.py."""

import json
from pathlib import Path

import pytest

from app.llm.disruption_interpreter import InterpretedDisruption, InterpretedMessage
from app.schemas.disruption import InterpretRequest
from app.services.disruption_service import interpret_disruption
from tests.services.multi_eval import case_problems, solve
from tests.services.test_sentences import DAYS, _minutes
from tests.services.test_substitute_finder import FakeLLM, FakePlaces, _details

CASES = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "multi_sentences.json").read_text("utf-8")
)


class _Fixed:
    def __init__(self, llm: dict) -> None:
        blank = dict.fromkeys(InterpretedDisruption.model_fields)
        self.answer = InterpretedMessage(
            events=[InterpretedDisruption(**{**blank, **e}) for e in llm["events"]],
            wishes=llm["wishes"],
        )

    def complete_json(self, *, system, user, schema):
        return self.answer


def read(case: dict, provider) -> tuple:
    day = DAYS[case["day"]]
    now = _minutes(case["now"])
    req = InterpretRequest(
        text=case["text"], now=now, location_id=case["at"], activities=day.activities
    )
    return day, now, interpret_disruption(req, provider)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_every_event_is_answered_by_every_candidate(case):
    day, now, res = read(case, _Fixed(case["llm"]))
    assert res.status == "ok", res.problem
    assert [e.type for e in res.events] == case["expect"]["types"]
    inp, out = solve(day, now, res)
    assert case_problems(case, inp, out) == []


def test_no_relaxed_copy_that_only_moves_the_day_later():
    """Decision 2026-11-27: without "쉬고 싶어", a relaxed candidate with the same pieces as another
    (only spread out later) is not shown; with the wish it stays, first."""
    case = next(c for c in CASES if c["id"] == "closed_and_later")
    day, now, res = read(case, _Fixed(case["llm"]))
    _, out = solve(day, now, res)
    assert [r.strategy for r in out.candidates] == ["balanced"]
    rest = {**case["llm"], "wishes": [{"wish": "rest", "evidence": "좀 쉬고 싶어"}]}
    day, now, res = read({**case, "text": case["text"] + ", 좀 쉬고 싶어"}, _Fixed(rest))
    _, out = solve(day, now, res)
    assert out.candidates[0].strategy == "relaxed"


def test_searched_places_show_up_in_the_candidates():
    """The live test solves the way POST /recoveries does (services/patch_search): rain on Tower
    Bridge, and an indoor place near it found by the search, is offered instead of dropping it."""

    from tests.services.multi_eval import in_words

    case = next(c for c in CASES if c["id"] == "rain_walk_less")
    rain = {
        "events": [{"type": "WEATHER", "time_from": None}],
        "wishes": [{"wish": "less_walking", "evidence": "덜 걷고"}],
    }
    day, now, res = read(case, _Fixed(rain))
    tower = next(a for a in day.activities if a.id == "tower")
    museum = _details("m1", tower.lat + 0.002, tower.lng, (540, 1260))
    places = FakePlaces({"m1": museum})
    found = places.search
    # Google's search hits carry the place types (indoor/outdoor is read from them).
    places.search = lambda *a, **k: [
        h.model_copy(update={"types": ("museum",)}) for h in found(*a, **k)
    ]
    inp, out = solve(day, now, res, FakeLLM(), places)
    assert any(s.replaces == "tower" for s in inp.substitutes)
    words = [w for r in out.candidates for w in in_words(inp, r)]
    assert any("타워 브리지: substitute → 가게 m1" in w for w in words), words
    assert case_problems({"expect": {}}, inp, out) == []


def test_a_wish_the_traveler_did_not_say_is_dropped():
    """Live test 2026-11-27: "도쿄타워 꼭 가고 싶어" came back with three wishes. A wish counts only
    when its evidence is the traveler's own words (spaces and punctuation aside)."""
    case = next(c for c in CASES if c["id"] == "tired_rain_rest")
    made_up = {
        **case["llm"],
        "wishes": [
            {"wish": "indoor", "evidence": "실내 에서!"},  # said, spaced differently
            {"wish": "rest", "evidence": ""},  # nothing to point to
            {"wish": "less_walking", "evidence": "덜 걷고 싶어"},  # not in this sentence
        ],
    }
    _, _, res = read(case, _Fixed(made_up))
    assert [w.value for w in res.wishes] == ["indoor"]


def test_the_same_event_heard_twice_is_one():
    case = next(c for c in CASES if c["id"] == "rain_walk_less")
    twice = {**case["llm"], "events": [{"type": "WEATHER"}, {"type": "WEATHER"}]}
    _, _, res = read(case, _Fixed(twice))
    assert sorted(e.type for e in res.events) == ["FATIGUE", "WEATHER"]


def test_a_closed_place_in_the_rain_is_searched_once():
    """Live test 2026-11-27: Tower Bridge closed AND raining was searched as closed and as
    outdoor, two substitutes with the same id -> the input was invalid (a 500 in the app)."""
    case = next(c for c in CASES if c["id"] == "closed_bridge_and_rain")
    day, now, res = read(case, _Fixed(case["llm"]))
    tower = next(a for a in day.activities if a.id == "tower")
    places = FakePlaces({"m1": _details("m1", tower.lat + 0.002, tower.lng, (540, 1260))})
    inp, out = solve(day, now, res, FakeLLM(), places)
    assert [s.id for s in inp.substitutes if s.replaces == "tower"] == ["sub_tower_1"]
    assert out.candidates


def test_a_bare_rain_next_to_a_timed_one_is_the_same_rain():
    """Live test: "15시까지 비" came back as WEATHER until 15:00 AND a bare WEATHER."""
    case = next(c for c in CASES if c["id"] == "rain_walk_less")
    both = {**case["llm"], "events": [{"type": "WEATHER", "time_to": "15:00"}, {"type": "WEATHER"}]}
    _, _, res = read(case, _Fixed(both))
    rains = [e for e in res.events if e.type == "WEATHER"]
    assert len(rains) == 1 and rains[0].end_time == 900
