"""Outer loop: try a few reordered plans and keep one only if it pays off.

The DP walks a fixed order, so D_order is 0 there. This tries two kinds of reordering, each
with its own budget, and solves each order again (through the same solve + validate path as
every candidate, so an order whose plan breaks a hard rule is simply discarded):

- swap: two neighbours trade places (A B C -> B A C).
- relocate: one activity is taken out and put back two or more places away (A B C D -> B C A D).
  An adjacent swap is the one-place case, so relocations skip it.

Separate budgets because travel saving ranks the two kinds differently: in one list, long
relocations crowd out the swap that helps (eval50, 2026-11-22). Within a kind, moves are tried
in order of travel saved, then shortest move, then position. The cheapest plan is adopted only
if RC drops by at least `min_gain`: changing the order is the change users notice most, so
small wins are not worth it. Tries are counted, not timed: the engine never reads the clock.
"""

from itertools import pairwise

from app.engine.candidate import original_order, solve_candidate
from app.engine.presets import Strategy
from app.schemas.models import HOTEL_ID
from app.schemas.recovery import RecoveryInput, RecoveryResult

EPS = 1e-9

Move = tuple[int, int]  # take order[i] out, then insert it so it ends up at position j


def _apply(order: tuple[str, ...], move: Move) -> tuple[str, ...]:
    i, j = move
    rest = [*order[:i], *order[i + 1 :]]
    rest.insert(j, order[i])
    return tuple(rest)


def _ranked(inp: RecoveryInput, order: tuple[str, ...], moves: list[Move]) -> list[Move]:
    """`moves` sorted by travel saved (whole route, event location to hotel), then shortest
    move, then earliest position."""
    table = {frozenset((t.a, t.b)): t.minutes for t in inp.travel}

    def leg(a: str, b: str) -> int:
        return 0 if a == b else table[frozenset((a, b))]

    def route(o: tuple[str, ...]) -> int:
        return sum(leg(a, b) for a, b in pairwise((inp.event.location_id, *o, HOTEL_ID)))

    now = route(order)
    saving = {m: now - route(_apply(order, m)) for m in moves}
    return sorted(moves, key=lambda m: (-saving[m], abs(m[0] - m[1]), m))


def _ranked_swaps(inp: RecoveryInput, order: tuple[str, ...]) -> list[Move]:
    return _ranked(inp, order, [(i, i + 1) for i in range(len(order) - 1)])


def _ranked_relocates(inp: RecoveryInput, order: tuple[str, ...]) -> list[Move]:
    n = len(order)
    moves = [(i, j) for i in range(n) for j in range(n) if abs(i - j) >= 2]
    return _ranked(inp, order, moves)


def improve_order(
    inp: RecoveryInput,
    strategy: Strategy,
    base: RecoveryResult,
    max_tries: int = 2,
    max_relocates: int = 2,
    min_gain: float = 0.10,
) -> RecoveryResult:
    """`base` must come from the original order. Returns base unless a reorder cuts RC enough.
    `max_tries` caps the swaps, `max_relocates` the relocations."""
    order = original_order(inp)
    tries = _ranked_swaps(inp, order)[:max_tries] + _ranked_relocates(inp, order)[:max_relocates]
    best = base
    for move in tries:
        result = solve_candidate(inp, strategy, _apply(order, move))
        if result is not None and result.rc_total < best.rc_total - EPS:
            best = result
    return best if best.rc_total <= base.rc_total * (1 - min_gain) else base
