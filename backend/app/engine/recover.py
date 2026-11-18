from app.engine.candidate import original_order, solve_candidate
from app.engine.local_search import improve_order
from app.engine.presets import STRATEGIES, Strategy
from app.engine.reasons import explain_changes
from app.schemas.recovery import RecoveryInput, RecoveryResult

__all__ = ["original_order", "recover", "solve_candidate"]  # re-exported for callers


def recover(
    inp: RecoveryInput,
    strategies: tuple[Strategy, ...] = STRATEGIES,
    max_tries: int = 2,
) -> list[RecoveryResult]:
    """Distinct candidates that passed the independent validator, one per strategy at most.

    Empty list = no valid plan. A strategy that yields the same plan as an earlier one adds
    nothing and is skipped. rc_total uses each strategy's own weights, so it is not
    comparable across candidates; the preservation rate is. solver_ms is left 0: the engine
    never reads the clock, the service layer fills it in. `max_tries` caps the order-swap
    attempts (0 = keep the original order); a count, not a time, so it stays deterministic.

    Order swapping is tried for the first strategy only (the representative candidate): on the
    eval set it tripled the time and improved the best plan in 1 of 50 scenarios, and that one
    was the first strategy's (decision 2026-11-18). The others keep the original order.
    """
    order = original_order(inp)
    results: list[RecoveryResult] = []
    seen: set[tuple] = set()
    for i, strategy in enumerate(strategies):
        result = solve_candidate(inp, strategy, order)
        if result is not None and i == 0:
            result = improve_order(inp, strategy, result, max_tries)
        if result is None or result.changes in seen:
            continue
        seen.add(result.changes)
        # Reasons only on the final candidates: the search above compares many plans.
        explained = explain_changes(inp, result.changes, strategy.min_buffer)
        results.append(result.model_copy(update={"changes": explained}))
    return results
