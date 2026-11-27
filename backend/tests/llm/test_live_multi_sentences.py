"""Several things at once, through the REAL model, REAL Google stand-in search and the engine:

    uv run python -m pytest -m live tests/llm/test_live_multi_sentences.py -s

Two questions per sentence: did the model hear every event (and wish), and does every patch
candidate answer all of them (tests/services/multi_eval.py)? The patch is made the way
POST /recoveries makes it (services/patch_search): closures, rain and dropped pieces get a Google
search for a stand-in nearby, so the new places show up too. Each candidate is written out in
words, with the places found, to tests/fixtures/multi_live_last.json, to judge by eye.
Costs per sentence: one LLM call to read it, and up to 2 + 2 searches (LLM query + Google).
"""

import json
from datetime import date
from pathlib import Path

import pytest

from app.llm.provider import interpret_provider
from app.services.places_client import GooglePlacesClient
from tests.services.multi_eval import case_problems, in_words, solve
from tests.services.test_multi_sentences import CASES, read

pytestmark = pytest.mark.live

RESULTS = Path(__file__).parents[1] / "fixtures" / "multi_live_last.json"
_seen: dict[str, dict] = {}


@pytest.fixture(scope="module")
def provider():
    return interpret_provider()


class _Watched:
    """The real Google client, noting failures: the app swallows them (a failed search = no
    stand-in), so without this an empty search and a broken one look the same."""

    def __init__(self) -> None:
        self.inner = GooglePlacesClient()
        self.errors: list[str] = []

    def _watch(self, name, *args, **kwargs):
        try:
            return getattr(self.inner, name)(*args, **kwargs)
        except Exception as e:
            self.errors.append(f"{name}: {type(e).__name__}: {str(e)[:160]}")
            raise

    def search(self, *args, **kwargs):
        return self._watch("search", *args, **kwargs)

    def details(self, *args, **kwargs):
        return self._watch("details", *args, **kwargs)


@pytest.fixture(scope="module")
def places():
    return _Watched()


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
def test_heard_and_answered(provider, places, case):
    day, now, res = read(case, provider)
    # A real date (a Wednesday), so Google's opening hours for that day are used for stand-ins.
    day = day.model_copy(update={"day": day.day.model_copy(update={"date": date(2026, 12, 2)})})
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
        places.errors.clear()
        inp, out = solve(day, now, res, provider, places)
        problems = case_problems(case, inp, out)
        record["places_found"] = [
            f"{s.title} (대신 {next(a.title for a in inp.activities if a.id == s.replaces)})"
            for s in inp.substitutes
        ]
        record["candidates"] = [
            {
                "strategy": r.strategy,
                "kept": round(r.preservation_rate, 2),
                "changes": in_words(inp, r),
            }
            for r in out.candidates
        ]
        record["blockers"] = [b.kind for b in out.blockers]
        record["google_errors"] = sorted(set(places.errors))
    record["problems"] = problems
    _seen[case["id"]] = record
    assert record["heard"] and not problems, record
