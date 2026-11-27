"""The 52 everyday sentences (tests/fixtures/sentences.json) through the REAL model.

    uv run pytest -m live tests/llm/test_live_sentences.py -s

tests/services/test_sentences.py checks the rules with a fixed reading of each sentence; this
checks the reading itself: does the model hear the same events and wishes a person would? One
LLM call per sentence (52 calls). A miss is printed with what the model wrote, so a prompt fix
can be aimed at it. The day each sentence is read against is the same as in test_sentences.
"""

import json
from pathlib import Path

import pytest

from app.llm.provider import OpenAIProvider
from app.schemas.disruption import InterpretRequest
from app.services.disruption_service import interpret_disruption
from tests.services.test_sentences import CASES, DAYS, _minutes

pytestmark = pytest.mark.live

RESULTS = Path(__file__).parents[1] / "fixtures" / "sentences_live_last.json"
_seen: dict[str, dict] = {}


@pytest.fixture(scope="module")
def provider():
    return OpenAIProvider()


@pytest.fixture(scope="module", autouse=True)
def _write_results():
    yield
    RESULTS.write_text(json.dumps(_seen, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    missed = [k for k, v in _seen.items() if not v["ok"]]
    print(f"\n{len(_seen) - len(missed)}/{len(_seen)} sentences read as expected")
    for k in missed:
        v = _seen[k]
        print(f"- {k}: want {v['want']} got {v['got']} | chips {v['chips']}")


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_the_model_hears_what_a_person_would(provider, case):
    day = DAYS[case["day"]]
    req = InterpretRequest(
        text=case["text"],
        now=_minutes(case["now"]),
        location_id=case["at"],
        activities=day.activities,
    )
    res = interpret_disruption(req, provider)
    want = case["expect"]
    got = {"status": res.status, "types": [e.type for e in res.events]}
    expected = {"status": want["status"], "types": want["types"]}
    ok = got == expected and (
        "wishes" not in want or [w.value for w in res.wishes] == want["wishes"]
    )
    _seen[case["id"]] = {
        "ok": ok,
        "want": expected | {"wishes": want.get("wishes")},
        "got": got | {"wishes": [w.value for w in res.wishes]},
        "chips": list(res.chips),
        "chips_match": "chips" not in want or list(res.chips) == want["chips"],
    }
    assert ok, _seen[case["id"]]
