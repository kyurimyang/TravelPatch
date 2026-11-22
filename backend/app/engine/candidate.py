from app.engine.constraint_builder import build_constraints
from app.engine.cost import compute_cost
from app.engine.optimizer_dp import solve_fixed_order
from app.engine.presets import Strategy
from app.engine.validator import Violation, validate
from app.schemas.enums import EventType
from app.schemas.events import FatigueEvent
from app.schemas.models import _Frozen
from app.schemas.recovery import RecoveryChange, RecoveryInput, RecoveryResult


def strategy_rules(strategy: Strategy) -> dict:
    """A strategy's own hard rules as validate() keywords (min_buffer is passed on its own)."""
    return {
        "reservation_buffer": strategy.reservation_buffer,
        "no_drop_categories": strategy.no_drop_categories,
    }


class Discard(_Frozen):
    """A candidate the validator rejected (CLAUDE.md 6: discard + log). Handed back as a value
    so the engine stays pure; the service layer writes the log. Normally never happens: one
    means the solver let a hard constraint through."""

    strategy: str
    violations: tuple[Violation, ...]


# Events the solver and validator actually handle. MUST_VISIT exists in the schema but is not
# implemented yet: it must be refused, not silently ignored.
SUPPORTED_EVENTS = frozenset(
    {
        EventType.DELAY,
        EventType.WEATHER,
        EventType.CLOSURE,
        EventType.FATIGUE,
        EventType.EXTEND,
        EventType.RESERVATION_CHANGE,
    }
)


class UnsupportedEventError(ValueError):
    """The event type has no solver support yet (CLAUDE.md rule 8: never guess)."""


def _flag_unknown_outdoor(
    inp: RecoveryInput, changes: tuple[RecoveryChange, ...]
) -> tuple[RecoveryChange, ...]:
    """In rain, activities whose outdoor status is unknown are kept but marked needs_check."""
    rain = build_constraints(inp).rain
    if rain is None:
        return changes
    unknown = {a.id for a in inp.activities if a.outdoor is None}
    return tuple(
        (
            c.model_copy(update={"needs_check": True})
            if c.activity_id in unknown
            and c.after is not None
            and c.after.start < rain[1]
            and c.after.end > rain[0]
            else c
        )
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
        (
            c.model_copy(update={"needs_check": True})
            if c.activity_id in unknown
            and c.after is not None
            and c.activity_id != inp.event.location_id
            else c
        )
        for c in changes
    )


def solve_candidate(
    inp: RecoveryInput,
    strategy: Strategy,
    order: tuple[str, ...],
    no_drop: frozenset[str] = frozenset(),
    discards: list[Discard] | None = None,
) -> RecoveryResult | None:
    """One candidate for one strategy, or None. The single path every plan takes to the user:
    solve, then the independent validator (a violating plan is discarded, never returned).
    A rejected plan is appended to `discards` when the caller passes a list."""
    if inp.event.type not in SUPPORTED_EVENTS:
        raise UnsupportedEventError(f"event type not supported yet: {inp.event.type}")
    solution = solve_fixed_order(
        inp,
        order,
        strategy.weights,
        strategy.min_buffer,
        no_drop=no_drop,
        reservation_buffer=strategy.reservation_buffer,
        no_drop_categories=strategy.no_drop_categories,
    )
    if solution is None:
        return None
    violations = validate(inp, solution.changes, strategy.min_buffer, **strategy_rules(strategy))
    if violations:
        if discards is not None:
            discards.append(Discard(strategy=strategy.name, violations=tuple(violations)))
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
