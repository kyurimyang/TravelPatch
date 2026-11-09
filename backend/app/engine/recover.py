from app.engine.candidate import original_order, solve_candidate
from app.engine.local_search import improve_order
from app.engine.presets import STRATEGIES, Strategy
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
    attempts per strategy (0 = keep the original order); a count, not a time, so it stays
    deterministic.
    """
    order = original_order(inp)
    results: list[RecoveryResult] = []
    seen: set[tuple] = set()
    for strategy in strategies:
        result = solve_candidate(inp, strategy, order)
        if result is not None:
            result = improve_order(inp, strategy, result, max_tries)
        if result is None or result.changes in seen:
            continue
        seen.add(result.changes)
        results.append(result)
    return results
