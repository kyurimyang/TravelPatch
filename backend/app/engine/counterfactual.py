"""Counterfactual: "what if we keep X?" for an activity a candidate dropped.

Pins X as undeletable and solves again with the SAME strategy, so the weights match and the
RC difference is meaningful. The new plan goes through the same solve + validate path as every
candidate. Pure: no I/O, no clock. The numbers in the user-facing sentence must come from this
result (reason_data), never from a language model.
"""

from app.engine.presets import STRATEGIES, Strategy
from app.engine.recover import original_order, solve_candidate
from app.schemas.enums import Op
from app.schemas.models import _Frozen
from app.schemas.recovery import RecoveryChange, RecoveryInput, RecoveryResult


class SideEffect(_Frozen):
    """Another activity whose change differs once X is kept."""

    activity_id: str
    before: RecoveryChange  # in the candidate the user was looking at
    after: RecoveryChange  # in the plan where X is kept


class Counterfactual(_Frozen):
    restored_id: str
    result: RecoveryResult
    d_preservation: float  # new - old; positive: more of the plan survives
    d_rc: float  # new - old under the same weights; positive: costlier
    side_effects: tuple[SideEffect, ...]  # ordered by activity id


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
    new = {c.activity_id: c for c in result.changes}
    effects = tuple(
        SideEffect(activity_id=i, before=old[i], after=new[i])
        for i in sorted(old)
        if i != activity_id and old[i] != new[i]
    )
    return Counterfactual(
        restored_id=activity_id,
        result=result,
        d_preservation=result.preservation_rate - base.preservation_rate,
        d_rc=result.rc_total - base.rc_total,
        side_effects=effects,
    )
