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
