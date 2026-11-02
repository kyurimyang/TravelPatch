"""Recovery Cost (RC) and preservation rate.

Assumes `changes` already passed the validator (every activity has exactly one entry).
Breakdown terms are raw D values (unweighted); rc_total applies the weights.
"""

from itertools import combinations, pairwise
from typing import NamedTuple

from app.engine.presets import DEFAULT_WEIGHTS, Weights
from app.schemas.enums import Op
from app.schemas.recovery import RcBreakdown, RecoveryChange, RecoveryInput


class Cost(NamedTuple):
    rc_total: float
    breakdown: RcBreakdown
    preservation_rate: float


def _route_minutes(ids: list[str], table: dict[frozenset[str], int]) -> int:
    return sum(table[frozenset(p)] for p in pairwise(ids))


def compute_cost(
    inp: RecoveryInput,
    changes: tuple[RecoveryChange, ...],
    weights: Weights = DEFAULT_WEIGHTS,
) -> Cost:
    # Float addition is order-dependent: fix the order so equal input gives identical bytes.
    changes = tuple(sorted(changes, key=lambda c: c.activity_id))
    values = {p.activity_id: p.tier.weight for p in inp.preferences}
    subst = {p.activity_id: p.substitutability for p in inp.preferences}
    by_id = {c.activity_id: c for c in changes}
    originals = sorted(inp.activities, key=lambda a: (a.planned_start, a.id))
    table = {frozenset((t.a, t.b)): t.minutes for t in inp.travel}

    category = {a.id: a.category for a in inp.activities}
    d_drop = sum(values[c.activity_id] for c in changes if c.op == Op.DROP)
    # Strategy presets can make some categories costlier to drop; the breakdown stays raw.
    weighted_drop = sum(
        weights.drop_factor(category[c.activity_id]) * values[c.activity_id]
        for c in changes
        if c.op == Op.DROP
    )

    d_shrink = 0.0
    for c in changes:
        if c.before is not None and c.after is not None:
            before_len = c.before.end - c.before.start
            after_len = c.after.end - c.after.start
            if after_len < before_len:
                d_shrink += values[c.activity_id] * (before_len - after_len) / before_len

    # New-place penalty is not modeled yet: substitute candidates carry no place data.
    d_sub = sum(
        values[c.activity_id] * (1 - subst[c.activity_id])
        for c in changes
        if c.op == Op.SUBSTITUTE
    )

    # Kendall tau distance: pairs of surviving activities whose relative order flipped.
    kept = [a.id for a in originals if by_id[a.id].after is not None]
    new_order = sorted(kept, key=lambda i: (by_id[i].after.start, i))
    rank = {i: r for r, i in enumerate(new_order)}
    d_order = float(sum(1 for x, y in combinations(kept, 2) if rank[x] > rank[y]))

    d_time = (
        sum(
            abs(c.after.start - c.before.start)
            for c in changes
            if c.before is not None and c.after is not None
        )
        / 60
    )

    placed = sorted(
        (c for c in changes if c.after is not None), key=lambda c: (c.after.start, c.activity_id)
    )
    original_travel = _route_minutes([a.id for a in originals], table)
    new_travel = _route_minutes([c.activity_id for c in placed], table)
    d_move = (new_travel - original_travel) / 60

    original_tags = {t for a in inp.activities for t in a.intent_tags}
    kept_tags = {t for a in inp.activities if by_id[a.id].after is not None for t in a.intent_tags}
    d_intent = float(len(original_tags - kept_tags))

    d_changed = float(sum(1 for c in changes if c.op != Op.KEEP))

    breakdown = RcBreakdown(
        d_drop=d_drop,
        d_shrink=d_shrink,
        d_sub=d_sub,
        d_order=d_order,
        d_time=d_time,
        d_move=d_move,
        d_intent=d_intent,
        d_changed=d_changed,
    )
    rc_total = (
        weights.w_drop * weighted_drop
        + weights.w_shrink * d_shrink
        + weights.w_sub * d_sub
        + weights.w_order * d_order
        + weights.w_time * d_time
        + weights.w_move * d_move
        + weights.w_intent * d_intent
        + weights.w_changed * d_changed
    )
    total_value = sum(values.values())
    preservation = 1 - (d_drop + d_shrink + d_sub) / total_value
    return Cost(rc_total, breakdown, max(0.0, min(1.0, preservation)))
