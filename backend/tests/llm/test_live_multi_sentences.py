"""Several things at once, through the REAL model and then the engine:

    uv run python -m pytest -m live tests/llm/test_live_multi_sentences.py -s

Two questions per sentence: did the model hear every event (and wish), and does every patch
candidate answer all of them (tests/services/multi_eval.py)? Each candidate is also written out in
words to tests/fixtures/multi_live_last.json, to judge by eye whether the alternatives make sense.
"""

import json
from pathlib import Path

import pytest

from app.llm.provider import OpenAIProvider
from tests.services.multi_eval import case_problems, in_words, solve
from tests.services.test_multi_sentences import CASES, read

pytestmark = pytest.mark.live

RESULTS = Path(__file__).parents[1] / "fixtures" / "multi_live_last.json"
_seen: dict[str, dict] = {}


@pytest.fixture(scope="module")
def provider():
    return OpenAIProvider()


@pytest.fixture(scope="module", autouse=True)
def _write_results():
    yield
    RESULTS.write_text(json.dumps(_seen, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    good = [k for k, v in _seen.items() if v["heard"] and not v["problems"]]
    print(f"\n{len(good)}/{len(_seen)} sentences heard right and answered right")
    for k, v in _seen.items():
        if k not in good:
            print(f"- {k}: heard {v['got_types']} (want {v['want_types']}) | {v['problems']}")


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_heard_and_answered(provider, case):
    day, now, res = read(case, provider)
    want = case["expect"]
    record = {
        "text": case["text"],
        "status": res.status,
        "want_types": want["types"],
        "got_types": [e.type for e in res.events],
        "wishes": [w.value for w in res.wishes],
        "chips": list(res.chips),
        "items": [
            {
                **i.draft.model_dump(exclude_none=True),
                "asked": i.question.text if i.event is None and i.question else None,
            }
            for i in res.items
        ],
    }
    record["heard"] = res.status == "ok" and sorted(record["got_types"]) == sorted(want["types"])
    problems: list[str] = []
    if res.status == "ok":
        inp, out = solve(day, now, res)
        problems = case_problems(case, inp, out)
        record["candidates"] = [
            {
                "strategy": r.strategy,
                "kept": round(r.preservation_rate, 2),
                "changes": in_words(inp, r),
            }
            for r in out.candidates
        ]
        record["blockers"] = [b.kind for b in out.blockers]
    record["problems"] = problems
    _seen[case["id"]] = record
    assert record["heard"] and not problems, record
