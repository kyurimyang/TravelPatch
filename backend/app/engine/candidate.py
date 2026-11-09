from app.engine.constraint_builder import build_constraints
from app.engine.cost import compute_cost
from app.engine.optimizer_dp import solve_fixed_order
from app.engine.presets import Strategy
from app.engine.validator import validate
from app.schemas.events import FatigueEvent
from app.schemas.recovery import RecoveryChange, RecoveryInput, RecoveryResult


def _flag_unknown_outdoor(
    inp: RecoveryInput, changes: tuple[RecoveryChange, ...]
) -> tuple[RecoveryChange, ...]:
    """In rain, activities whose outdoor status is unknown are kept but marked needs_check."""
    rain = build_constraints(inp).rain
    if rain is None:
        return changes
    unknown = {a.id for a in inp.activities if a.outdoor is None}
    return tuple(
        c.model_copy(update={"needs_check": True})
        if c.activity_id in unknown
        and c.after is not None
        and c.after.start < rain[1]
        and c.after.end > rain[0]
        else c
        for c in changes
    )


def _flag_unknown_walking(
    inp: RecoveryInput, changes: tuple[RecoveryChange, ...]
) -> tuple[RecoveryChange, ...]:
    """When tired, activities whose walking load is unknown are kept but marked needs_check."""
    if not isinstance(inp.event, FatigueEvent):
        return changes
    unknown = {a.id for a in inp.activities if a.walking is None}
    return tuple(
        c.model_copy(update={"needs_check": True})
        if c.activity_id in unknown and c.after is not None and c.activity_id != inp.event.location_id
        else c
        for c in changes
    )


def solve_candidate(
    inp: RecoveryInput,
    strategy: Strategy,
    order: tuple[str, ...],
    no_drop: frozenset[str] = frozenset(),
) -> RecoveryResult | None:
    """One candidate for one strategy, or None. The single path every plan takes to the user:
    solve, then the independent validator (a violating plan is discarded, never returned)."""
    solution = solve_fixed_order(inp, order, strategy.weights, strategy.min_buffer, no_drop=no_drop)
    if solution is None or validate(inp, solution.changes, strategy.min_buffer):
        return None
    # Changes always come out in the original order, whatever order the solver walked.
    position = {act_id: n for n, act_id in enumerate(original_order(inp))}
    changes = tuple(sorted(solution.changes, key=lambda c: position[c.activity_id]))
    cost = compute_cost(inp, changes, strategy.weights)
    return RecoveryResult(
        strategy=strategy.name,
        changes=_flag_unknown_walking(inp, _flag_unknown_outdoor(inp, changes)),
        rc_total=cost.rc_total,
        rc_breakdown=cost.breakdown,
        preservation_rate=cost.preservation_rate,
        violations=0,
        solver_ms=0,
    )


def original_order(inp: RecoveryInput) -> tuple[str, ...]:
    return tuple(a.id for a in sorted(inp.activities, key=lambda a: (a.planned_start, a.id)))
