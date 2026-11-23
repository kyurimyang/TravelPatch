import json
from pathlib import Path

from app.engine.recover import recover
from app.engine.relax import relaxations
from app.schemas.enums import Tier
from app.schemas.recovery import RecoveryInput

SCENARIOS = Path(__file__).parents[1] / "scenarios"


def _scenario(name: str) -> RecoveryInput:
    raw = json.loads((SCENARIOS / name).read_text(encoding="utf-8"))
    raw.pop("expected", None)
    return RecoveryInput.model_validate(raw)


def test_a_failing_day_names_the_one_must_that_blocks_it() -> None:
    # a0 is a reserved must at 9:55 and the delay runs to 10:25: no plan keeps it.
    inp = _scenario("eval50/i02_delay.json")
    assert recover(inp) == []
    found = relaxations(inp)
    assert [r.activity_id for r in found] == ["a0"]
    assert 0 < found[0].preservation_rate < 1


def test_the_suggestion_holds_when_the_client_asks_again_with_it() -> None:
    # The client re-asks with a0 as "nice"; the normal path must then find a valid plan.
    inp = _scenario("eval50/i02_delay.json")
    prefs = tuple(
        p.model_copy(update={"tier": Tier.NICE}) if p.activity_id == "a0" else p
        for p in inp.preferences
    )
    results = recover(inp.model_copy(update={"preferences": prefs}))
    assert results and all(r.violations == 0 for r in results)


def test_several_suggestions_come_best_first() -> None:
    found = relaxations(_scenario("eval50/i07_weather.json"))
    rates = [r.preservation_rate for r in found]
    assert rates == sorted(rates, reverse=True)


def test_a_day_with_no_must_has_nothing_to_relax() -> None:
    # i04_extend fails on the asked-for extension itself, not on a must.
    assert relaxations(_scenario("eval50/i04_extend.json")) == []
