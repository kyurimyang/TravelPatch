"""Sentences people actually type on the "한 줄로 알려 주세요" field (fixtures/sentences.json).

The LLM is a fake that returns the reading fixed in the fixture: only what the sentence says.
That keeps the test on the rule step (gaps filled, places matched, times computed, questions
asked) and on the engine behind it: every built answer goes on to a full recovery whose
candidates must all pass the independent validator.
"""

import json
from pathlib import Path

import pytest

from app.engine.candidate import strategy_rules
from app.engine.presets import STRATEGIES
from app.engine.validator import validate
from app.llm.disruption_interpreter import InterpretedDisruption, InterpretedMessage
from app.schemas.disruption import InterpretRequest
from app.schemas.enums import Category, Tier, TimeRigidity
from app.schemas.models import Activity, Day, Preference
from app.schemas.recovery import RecoveryInput
from app.services.disruption_service import interpret_disruption
from app.services.recovery_service import run_recovery
from app.services.travel_estimate import fill_missing_travel
from app.services.visited import apply_visited
from tests.engine.helpers import load_scenario_a

CASES = json.loads((Path(__file__).parents[1] / "fixtures" / "sentences.json").read_text("utf-8"))


def _london() -> RecoveryInput:
    """A London day with a booked London Eye (15:00), lunch at noon and two outdoor walks."""
    hotel = (51.5117, -0.1240)
    rows = [
        # id, title, category, start, end, min, outdoor, walking, booked, tier
        ("museum", "대영박물관", Category.SIGHTSEEING, 570, 690, 60, False, True, None, Tier.NICE),
        ("lunch", "Dishoom 코벤트가든", Category.MEAL, 720, 790, 40, False, False, None, Tier.MUST),
        (
            "southbank",
            "사우스뱅크 산책",
            Category.SIGHTSEEING,
            810,
            870,
            30,
            True,
            True,
            None,
            Tier.OPTIONAL,
        ),
        ("eye", "런던 아이", Category.SIGHTSEEING, 900, 945, 45, None, False, 900, Tier.MUST),
        ("tower", "타워 브리지", Category.SIGHTSEEING, 990, 1050, 30, True, True, None, Tier.NICE),
        ("pub", "저녁 펍", Category.MEAL, 1140, 1230, 60, False, False, None, Tier.NICE),
    ]
    coords = {
        "museum": (51.5194, -0.1270),
        "lunch": (51.5124, -0.1260),
        "southbank": (51.5065, -0.1160),
        "eye": (51.5033, -0.1196),
        "tower": (51.5055, -0.0754),
        "pub": (51.5130, -0.1310),
    }
    acts = tuple(
        Activity(
            id=i,
            title=t,
            category=c,
            lat=coords[i][0],
            lng=coords[i][1],
            planned_start=s,
            planned_end=e,
            min_duration=m,
            outdoor=o,
            walking=w,
            reservation_time=r,
        )
        for i, t, c, s, e, m, o, w, r, _ in rows
    )
    prefs = tuple(
        Preference(
            activity_id=i,
            tier=tier,
            substitutability=0.4,
            time_rigidity=TimeRigidity.RESERVED if r is not None else TimeRigidity.FLEXIBLE,
        )
        for i, *_, r, tier in rows
    )
    points = {a.id: (a.lat, a.lng) for a in acts} | {"hotel": hotel}
    return RecoveryInput(
        day=Day(
            id="london-day",
            timezone="Europe/London",
            start_time=540,
            end_deadline=1380,
            end_lat=hotel[0],
            end_lng=hotel[1],
        ),
        activities=acts,
        preferences=prefs,
        travel=fill_missing_travel(points),
        event={"type": "DELAY", "occurred_at": 540, "start_time": 540},
    )


DAYS = {"tokyo": load_scenario_a(), "london": _london()}


class FakeProvider:
    def __init__(self, answer: InterpretedMessage) -> None:
        self.answer = answer
        self.calls = 0

    def complete_json(self, *, system, user, schema):
        self.calls += 1
        assert schema is InterpretedMessage
        return self.answer


def _reading(llm: dict) -> InterpretedMessage:
    blank = dict.fromkeys(InterpretedDisruption.model_fields)
    return InterpretedMessage(
        events=[InterpretedDisruption(**{**blank, **e}) for e in llm["events"]],
        wishes=llm["wishes"],
    )


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _ask(case):
    day = DAYS[case["day"]]
    req = InterpretRequest(
        text=case["text"],
        now=_minutes(case["now"]),
        location_id=case["at"],
        activities=day.activities,
    )
    provider = FakeProvider(_reading(case["llm"]))
    res = interpret_disruption(req, provider)
    assert provider.calls == 1
    return day, req, res


def test_there_are_about_fifty_sentences():
    assert len(CASES) >= 50
    assert len({c["id"] for c in CASES}) == len(CASES)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_rules_understand_the_sentence(case):
    _, _, res = _ask(case)
    want = case["expect"]
    assert res.status == want["status"], res
    assert [e.type for e in res.events] == want["types"]
    if "chips" in want:
        assert list(res.chips) == want["chips"]
    if "wishes" in want:
        assert [w.value for w in res.wishes] == want["wishes"]
    if res.status == "ok":
        assert res.problem is None and res.event == res.events[0]
    else:
        assert res.event is None and res.problem is not None
        # Asked in words, never with a field name.
        assert "_" not in res.problem.detail and not any(
            f in res.problem.detail for f in ("time_from", "activity", "minutes", "hint")
        )
    if "ask" in want:
        assert res.problem.detail == want["ask"]
    if "candidates" in want:
        assert sorted(res.problem.candidates) == sorted(want["candidates"])
    if "code" in want:
        assert res.problem.code == want["code"]
    # Understood events are never thrown away because another one is missing a value.
    # (A wish alone has no items: its event is the day going on from now.)
    built = [i for i in res.items if i.event is not None]
    assert len(built) >= len(res.events) or not res.items


OK_CASES = [c for c in CASES if c["expect"]["status"] == "ok"]


@pytest.mark.parametrize("case", OK_CASES, ids=[c["id"] for c in OK_CASES])
def test_the_engine_answers_with_valid_patches(case):
    day, req, res = _ask(case)
    data = day.model_dump()
    data |= {
        "event": res.events[0].model_dump(),
        "more_events": [e.model_dump() for e in res.events[1:]],
        "wishes": [w.value for w in res.wishes],
    }
    inp = RecoveryInput.model_validate(data)
    # What ended before now was visited (the app pre-ticks the same), except what an event is about.
    targets = {getattr(e, "activity_id", None) for e in res.events}
    visited = [a.id for a in inp.activities if a.planned_end <= req.now and a.id not in targets]
    inp = apply_visited(inp, visited)
    out = run_recovery(inp)
    want = case["expect"]
    if want.get("patch", True):
        assert out.candidates, (out.blockers, out.relaxations)
    else:
        assert not out.candidates and (out.blockers or out.relaxations)
    by_name = {s.name: s for s in STRATEGIES}
    for result in out.candidates:
        strategy = by_name[result.strategy]
        assert validate(inp, result.changes, strategy.min_buffer, **strategy_rules(strategy)) == []
        assert result.violations == 0
    if "first_strategy" in want:
        assert out.candidates[0].strategy == want["first_strategy"]
    if want.get("distinct_candidates"):
        assert len({r.changes for r in out.candidates}) == len(out.candidates) > 1
