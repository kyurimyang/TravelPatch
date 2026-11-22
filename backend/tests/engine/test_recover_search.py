"""Order search runs only for strategies with `search_order` (balanced, low_travel).

History: on 2026-11-18 it ran for the first strategy only (speed option A): adjacent swaps
tripled the time and improved one plan in 50. On 2026-11-22 relocations were added and
low_travel was switched on too, since a "least travel" plan that can never reorder its stops
did not do what its name says. The other strategies are solved in the original order only.
"""

import json
from pathlib import Path

from app.engine.presets import STRATEGIES
from app.engine.recover import recover
from app.schemas.recovery import RecoveryInput
from tests.engine.helpers import load_scenario_a

EVAL = Path(__file__).parents[1] / "scenarios" / "eval50"
SEARCHED = [s.name for s in STRATEGIES if s.search_order]


def _load(name: str) -> RecoveryInput:
    raw = json.loads((EVAL / f"{name}.json").read_text(encoding="utf-8"))
    raw.pop("expected", None)
    return RecoveryInput.model_validate(raw)


def test_balanced_and_low_travel_search_the_order() -> None:
    assert SEARCHED == ["balanced", "low_travel"]


def test_the_first_strategy_still_gets_the_better_order() -> None:
    inp = _load("i00_delay")
    first = next(r for r in recover(inp) if r.strategy == STRATEGIES[0].name)
    assert round(first.preservation_rate, 4) == 0.9514  # 0.8333 without order search


def test_other_strategies_keep_the_original_order() -> None:
    # Compared one strategy at a time: recover() drops a candidate equal to an earlier one, so
    # the two runs may list different strategies.
    by_name = {s.name: s for s in STRATEGIES}
    for inp in (load_scenario_a(), _load("i07_delay"), _load("i01_closure")):
        for result in recover(inp):
            if result.strategy in SEARCHED:
                continue
            (plain,) = recover(inp, strategies=(by_name[result.strategy],), max_tries=0)
            assert result == plain


def test_order_search_is_tried_for_flagged_strategies_only(monkeypatch) -> None:
    import app.engine.recover as rec

    tried: list[str] = []
    real = rec.improve_order

    def spy(inp, strategy, result, max_tries, max_relocates):
        tried.append(strategy.name)
        return real(inp, strategy, result, max_tries, max_relocates)

    monkeypatch.setattr(rec, "improve_order", spy)
    recover(load_scenario_a(), limit=None)
    assert tried == SEARCHED
