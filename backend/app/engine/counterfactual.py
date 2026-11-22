"""Counterfactual: "what if we keep X?" for an activity a candidate dropped.

Pins X as undeletable and solves again with the SAME strategy, so the weights match and the
RC difference is meaningful. The new plan goes through the same solve + validate path as every
candidate. Pure: no I/O, no clock. The numbers in the user-facing sentence must come from this
result (reason_data), never from a language model.
"""

from app.engine.candidate import strategy_rules
from app.engine.presets import STRATEGIES, Strategy
from app.engine.reasons import explain_changes
from app.engine.recover import original_order, solve_candidate
from app.schemas.enums import Op
from app.schemas.recovery import (
    Counterfactual,
    RecoveryChange,
    RecoveryInput,
    RecoveryResult,
    SideEffect,
)


def restore(
    inp: RecoveryInput,
    base: RecoveryResult,
    activity_id: str,
    strategies: tuple[Strategy, ...] = STRATEGIES,
) -> Counterfactual | None:
    """None = no valid plan keeps X. ValueError = X was not dropped in `base` (nothing to restore)."""
    old = {c.activity_id: c for c in base.changes}
    if activity_id not in old or old[activity_id].op != Op.DROP:
        raise ValueError(f"{activity_id} is not dropped in the {base.strategy} candidate")
    strategy = next((s for s in strategies if s.name == base.strategy), None)
    if strategy is None:
        raise ValueError(f"unknown strategy: {base.strategy}")

    result = solve_candidate(inp, strategy, original_order(inp), frozenset({activity_id}))
    if result is None:
        return None
    result = result.model_copy(
        update={"changes": explain_changes(
            inp, result.changes, strategy.min_buffer, **strategy_rules(strategy)
        )}
    )
    new = {c.activity_id: c for c in result.changes}
    effects = tuple(
        SideEffect(activity_id=i, before=old[i], after=new[i])
        for i in sorted(old)
        if i != activity_id and _differs(old[i], new[i])
    )
    return Counterfactual(
        restored_id=activity_id,
        result=result,
        d_preservation=result.preservation_rate - base.preservation_rate,
        d_rc=result.rc_total - base.rc_total,
        side_effects=effects,
    )


def _differs(a: RecoveryChange, b: RecoveryChange) -> bool:
    # What the plan does with the activity. The reason text may differ without the plan differing.
    return (a.op, a.before, a.after, a.substitute_id) != (b.op, b.before, b.after, b.substitute_id)
