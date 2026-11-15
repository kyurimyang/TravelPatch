import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from eval.llm_baselines import (
    REPAIRS,
    CachedProvider,
    NoPlan,
    make_llm_only,
    make_llm_validated,
)
from eval.llm_plan import LLMPlan, PlanItem, hhmm

from app.engine.recover import recover
from app.llm.provider import LLMOutputError
from app.schemas.recovery import RecoveryInput


@pytest.fixture(scope="module")
def inp() -> RecoveryInput:
    raw = json.loads((ROOT / "backend/tests/scenarios/scenario_a.json").read_text(encoding="utf-8"))
    raw.pop("expected", None)
    return RecoveryInput.model_validate(raw)


class Scripted:
    """Returns queued plans (or raises), counting calls."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = 0

    def complete_json(self, *, system, user, schema):
        self.calls += 1
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def _provider(tmp_path, answers):
    inner = Scripted(answers)
    return inner, CachedProvider(inner, tmp_path, "test-model")


KEEP_ALL = LLMPlan(items=[])  # nothing said = unchanged: breaks scenario A (user is late)


def _engine_plan(inp) -> LLMPlan:
    """The engine's best candidate written as an LLM answer: known to be valid."""
    best = max(recover(inp), key=lambda r: r.preservation_rate)
    items = []
    for c in best.changes:
        if c.after is None:
            items.append(PlanItem(activity_id=c.activity_id, action="drop", start=None, end=None))
        else:
            items.append(
                PlanItem(
                    activity_id=c.activity_id,
                    action="change",
                    start=hhmm(c.after.start),
                    end=hhmm(c.after.end),
                )
            )
    return LLMPlan(items=items)


def _wrong_plans(inp, n):
    """n different invalid answers (distinct prompts, so the cache cannot merge the calls)."""
    first = inp.activities[0].id
    return [
        LLMPlan(items=[PlanItem(activity_id=first, action="keep", start=None, end=None)] * (i + 1))
        for i in range(n)
    ]


def test_cache_returns_recorded_answer_without_calling_again(tmp_path):
    inner, provider = _provider(tmp_path, [KEEP_ALL])
    first = provider.complete_json(system="s", user="u", schema=LLMPlan)
    second = provider.complete_json(system="s", user="u", schema=LLMPlan)
    assert first == second and inner.calls == 1
    assert provider.take_ms() >= 0 and provider.ms == 0.0


def test_llm_only_reports_violations_instead_of_hiding_them(inp, tmp_path):
    _, provider = _provider(tmp_path, [KEEP_ALL])
    result = make_llm_only(provider)(inp)
    assert result.violations > 0 and result.strategy == "llm_only"


def test_llm_error_becomes_no_plan(inp, tmp_path):
    _, provider = _provider(tmp_path, [LLMOutputError("refused")])
    with pytest.raises(NoPlan) as info:
        make_llm_only(provider)(inp)
    assert info.value.reason == "llm_error"


def test_validated_rejects_after_repairs_run_out(inp, tmp_path):
    inner, provider = _provider(tmp_path, _wrong_plans(inp, 1 + REPAIRS))
    with pytest.raises(NoPlan) as info:
        make_llm_validated(provider)(inp)
    assert info.value.reason == "validator_rejected"
    assert inner.calls == 1 + REPAIRS  # first answer + the repairs, then it stops


def test_validated_stops_at_the_first_clean_plan(inp, tmp_path):
    inner, provider = _provider(tmp_path, [KEEP_ALL, _engine_plan(inp), KEEP_ALL])
    result = make_llm_validated(provider)(inp)
    assert result.violations == 0 and result.strategy == "llm_validated"
    assert inner.calls == 2  # one bad answer, one repair, then it stops
