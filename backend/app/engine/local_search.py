"""Outer loop: try swapping neighbouring activities and keep the order only if it pays off.

The DP walks a fixed order, so D_order is 0 there. This tries a few adjacent swaps, solves each
again (through the same solve + validate path as every candidate, so an order whose plan breaks
a hard rule is simply discarded) and adopts the cheapest one, but only if RC drops by at least
`min_gain`: changing the order is the change users notice most, so small wins are not worth it.
Tries are counted, not timed: the engine never reads the clock.
"""

from itertools import pairwise

from app.engine.candidate import original_order, solve_candidate
from app.engine.presets import Strategy
from app.schemas.models import HOTEL_ID
from app.schemas.recovery import RecoveryInput, RecoveryResult

EPS = 1e-9


def _ranked_swaps(inp: RecoveryInput, order: tuple[str, ...]) -> list[int]:
    """Positions i (swap order[i], order[i+1]), best travel saving first, then earliest."""
    table = {frozenset((t.a, t.b)): t.minutes for t in inp.travel}

    def leg(a: str, b: str) -> int:
        return 0 if a == b else table[frozenset((a, b))]

    def route(nodes: list[str]) -> int:
        return sum(leg(a, b) for a, b in pairwise(nodes))

    saving: dict[int, int] = {}
    for i in range(len(order) - 1):
        before = inp.event.location_id if i == 0 else order[i - 1]
        after = order[i + 2] if i + 2 < len(order) else HOTEL_ID
        a, b = order[i], order[i + 1]
        saving[i] = route([before, a, b, after]) - route([before, b, a, after])
    return sorted(saving, key=lambda i: (-saving[i], i))


def improve_order(
    inp: RecoveryInput,
    strategy: Strategy,
    base: RecoveryResult,
    max_tries: int = 2,
    min_gain: float = 0.10,
) -> RecoveryResult:
    """`base` must come from the original order. Returns base unless a swap cuts RC enough."""
    order = original_order(inp)
    best = base
    for i in _ranked_swaps(inp, order)[:max_tries]:
        swapped = (*order[:i], order[i + 1], order[i], *order[i + 2 :])
        result = solve_candidate(inp, strategy, swapped)
        if result is not None and result.rc_total < best.rc_total - EPS:
            best = result
    return best if best.rc_total <= base.rc_total * (1 - min_gain) else base
