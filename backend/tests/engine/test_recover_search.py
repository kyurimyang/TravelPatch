"""Local search runs on the first strategy only (decision 2026-11-18, speed option A).

Measured on eval50: order swapping tripled the time and improved the best plan in 1 of 50
scenarios (i07_delay, the balanced candidate). Since the meal window (2026-11-19) that gain was
lunch 145 min late and is gone; the one gain left is i00_delay (83.3% -> 95.1%). The other
strategies are solved in the original order only.
"""

import json
from pathlib import Path

from app.engine.presets import STRATEGIES
from app.engine.recover import recover
from app.schemas.recovery import RecoveryInput
from tests.engine.helpers import load_scenario_a

EVAL = Path(__file__).parents[1] / "scenarios" / "eval50"


def _load(name: str) -> RecoveryInput:
    raw = json.loads((EVAL / f"{name}.json").read_text(encoding="utf-8"))
    raw.pop("expected", None)
    return RecoveryInput.model_validate(raw)


def test_the_first_strategy_still_gets_the_better_order() -> None:
    inp = _load("i00_delay")
    first = next(r for r in recover(inp) if r.strategy == STRATEGIES[0].name)
    assert round(first.preservation_rate, 4) == 0.9514  # 0.8333 without order swapping


def test_other_strategies_keep_the_original_order() -> None:
    # Compared one strategy at a time: recover() drops a candidate equal to an earlier one, so
    # the two runs may list different strategies.
    by_name = {s.name: s for s in STRATEGIES}
    for inp in (load_scenario_a(), _load("i07_delay"), _load("i01_closure")):
        for result in recover(inp):
            if result.strategy == STRATEGIES[0].name:
                continue
            (plain,) = recover(inp, strategies=(by_name[result.strategy],), max_tries=0)
            assert result == plain


def test_local_search_is_tried_for_the_first_strategy_only(monkeypatch) -> None:
    import app.engine.recover as rec

    tried: list[str] = []
    real = rec.improve_order

    def spy(inp, strategy, result, max_tries):
        tried.append(strategy.name)
        return real(inp, strategy, result, max_tries)

    monkeypatch.setattr(rec, "improve_order", spy)
    recover(load_scenario_a())
    assert tried == [STRATEGIES[0].name]
