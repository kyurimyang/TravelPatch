from app.engine.candidate import Discard, original_order, solve_candidate, strategy_rules
from app.engine.constraint_builder import solver_view
from app.engine.local_search import improve_order
from app.engine.presets import SHOWN_CANDIDATES, STRATEGIES, Strategy
from app.engine.reasons import explain_changes
from app.schemas.recovery import RecoveryInput, RecoveryResult

__all__ = ["Discard", "original_order", "recover", "solve_candidate"]  # re-exported for callers


def recover(
    inp: RecoveryInput,
    strategies: tuple[Strategy, ...] = STRATEGIES,
    max_tries: int = 2,
    discards: list[Discard] | None = None,
    limit: int | None = SHOWN_CANDIDATES,
) -> list[RecoveryResult]:
    """Distinct candidates that passed the independent validator, one per strategy at most.

    Empty list = no valid plan. A strategy that yields the same plan as an earlier one adds
    nothing and is skipped. rc_total uses each strategy's own weights, so it is not
    comparable across candidates; the preservation rate is. solver_ms is left 0: the engine
    never reads the clock, the service layer fills it in. `max_tries` caps the reorder
    attempts of each kind, swaps and relocations (0 = keep the original order); a count, not
    a time, so it stays deterministic.

    The order is searched only for strategies with `search_order` (balanced and low_travel,
    decisions 2026-11-18 and 2026-11-22): it is the slow part. The others keep the original
    order.

    `discards`, when given, collects the candidates the validator rejected (for the log).
    `limit` keeps the first candidate and then the ones most unlike those kept (None: all).
    """
    order = original_order(inp)
    results: list[RecoveryResult] = []
    seen: set[tuple] = set()
    for i, strategy in enumerate(strategies):
        if _same_as_earlier(inp, strategy, strategies[:i]):
            continue  # its rules have nothing to act on today: an earlier strategy is identical
        result = solve_candidate(inp, strategy, order, discards=discards)
        if result is not None and strategy.search_order:
            result = improve_order(inp, strategy, result, max_tries, max_tries)
        if result is None or result.changes in seen:
            continue
        seen.add(result.changes)
        # Reasons only on the final candidates: the search above compares many plans.
        explained = explain_changes(
            inp, result.changes, strategy.min_buffer, **strategy_rules(strategy)
        )
        results.append(result.model_copy(update={"changes": explained}))
    return _most_distinct(results, limit)


def _effective(inp: RecoveryInput, strategy: Strategy) -> Strategy:
    """The strategy without rules that cannot act on this day (no booking, no such category)."""
    view = solver_view(inp)  # a moved booking still counts as a booking
    booked = any(a.reservation_time is not None for a in view.activities)
    present = {a.category for a in view.activities}
    return strategy.model_copy(
        update={
            "name": "",
            # Same rules but no order search is still a copy (as before search_order existed).
            "search_order": False,
            "reservation_buffer": strategy.reservation_buffer if booked else 0,
            "no_drop_categories": tuple(c for c in strategy.no_drop_categories if c in present),
        }
    )


def _same_as_earlier(inp: RecoveryInput, strategy: Strategy, earlier: tuple[Strategy, ...]) -> bool:
    """Exactly the computation of an earlier strategy: same weights, same effective rules."""
    mine = _effective(inp, strategy)
    return any(_effective(inp, e) == mine for e in earlier)


def shown_distance(a: RecoveryResult, b: RecoveryResult) -> int:
    """How many activities two candidates treat differently (op, slot or place)."""
    key = {c.activity_id: (c.op, c.after, c.substitute_id) for c in b.changes}
    return sum(key.get(c.activity_id) != (c.op, c.after, c.substitute_id) for c in a.changes)


def _most_distinct(results: list[RecoveryResult], limit: int | None) -> list[RecoveryResult]:
    """The first (balanced) candidate, then greedily the one farthest from all kept so far:
    different choices rather than near copies. Ties: higher preservation, then strategy order."""
    if limit is None or len(results) <= limit:
        return results
    kept, rest = results[:1], list(results[1:])
    while len(kept) < limit and rest:
        best = max(
            rest,
            key=lambda r: (
                min(shown_distance(r, k) for k in kept),
                r.preservation_rate,
                -results.index(r),
            ),
        )
        kept.append(best)
        rest.remove(best)
    return kept
