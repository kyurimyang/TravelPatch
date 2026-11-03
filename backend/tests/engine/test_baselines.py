from app.engine.baselines import greedy, right_shift
from app.engine.validator import validate
from app.schemas.enums import Op, Tier
from app.schemas.events import DelayEvent
from app.schemas.recovery import RecoveryInput
from tests.engine.helpers import load_scenario_a

BASELINES = (right_shift, greedy)


def _with_tiers(inp: RecoveryInput, **tiers: Tier) -> RecoveryInput:
    prefs = tuple(
        p.model_copy(update={"tier": tiers[p.activity_id]}) if p.activity_id in tiers else p
        for p in inp.preferences
    )
    return inp.model_copy(update={"preferences": prefs})


def _dropped(result) -> set[str]:
    return {c.activity_id for c in result.changes if c.op == Op.DROP}


def test_nothing_happened_keeps_everything() -> None:
    inp = load_scenario_a()
    calm = inp.model_copy(update={"event": DelayEvent(occurred_at=0, start_time=0)})
    for baseline in BASELINES:
        result = baseline(calm)
        assert {c.op for c in result.changes} == {Op.KEEP}
        assert result.violations == 0
        assert result.preservation_rate == 1.0


def test_baselines_cover_every_activity_and_never_shrink() -> None:
    inp = load_scenario_a()
    ids = {a.id for a in inp.activities}
    for baseline in BASELINES:
        result = baseline(inp)
        assert {c.activity_id for c in result.changes} == ids
        assert Op.SHRINK not in {c.op for c in result.changes}  # baselines cannot shorten


def test_violations_field_matches_independent_validator() -> None:
    inp = load_scenario_a()
    for baseline in BASELINES:
        result = baseline(inp)
        assert result.violations == len(validate(inp, result.changes))


def test_deterministic() -> None:
    inp = load_scenario_a()
    for baseline in BASELINES:
        assert baseline(inp) == baseline(inp)


def test_must_is_never_dropped_even_when_it_cannot_fit() -> None:
    inp = load_scenario_a()
    late = inp.model_copy(update={"event": DelayEvent(occurred_at=1100, start_time=1100)})
    for baseline in BASELINES:
        result = baseline(late)
        must = {p.activity_id for p in late.preferences if p.tier == Tier.MUST}
        assert not _dropped(result) & must
        assert result.violations > 0  # a baseline cannot fix this; it only reports it


def test_right_shift_drops_by_position_greedy_by_value() -> None:
    # Make the later cafe worth more than the earlier shop: both are droppable when the
    # day overflows, but the baselines pick different victims.
    inp = _with_tiers(load_scenario_a(), shibuya_shop=Tier.OPTIONAL, cafe=Tier.NICE)
    shifted = right_shift(inp)
    value_based = greedy(inp)
    assert _dropped(shifted)  # the delay overflows the day, something must go
    assert _dropped(value_based)
    assert "cafe" in _dropped(shifted) or "shibuya_shop" not in _dropped(shifted)
    assert "shibuya_shop" in _dropped(value_based)
    assert _dropped(shifted) != _dropped(value_based)
