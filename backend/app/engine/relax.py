"""Relaxations: when no plan exists, which single "must" stands in the way?

For each must activity, the same day with only that one taken down to "nice" is solved with the
default strategy (the one with no extra rules of its own). Those that give a valid plan are
returned, best preservation first. Pure: no I/O, no clock. Only called when recover() came back
empty, so its cost is paid on the rare failing day only.
"""

from app.engine.presets import STRATEGIES, Strategy
from app.engine.recover import recover
from app.schemas.enums import Tier
from app.schemas.recovery import RecoveryInput, Relaxation


def relaxations(
    inp: RecoveryInput, strategies: tuple[Strategy, ...] = STRATEGIES[:1]
) -> list[Relaxation]:
    found: list[Relaxation] = []
    for pref in inp.preferences:
        if pref.tier != Tier.MUST:
            continue
        prefs = tuple(
            p.model_copy(update={"tier": Tier.NICE}) if p.activity_id == pref.activity_id else p
            for p in inp.preferences
        )
        results = recover(inp.model_copy(update={"preferences": prefs}), strategies, limit=1)
        if results:
            found.append(
                Relaxation(
                    activity_id=pref.activity_id, preservation_rate=results[0].preservation_rate
                )
            )
    # Ties keep the input order, so equal input gives equal output.
    return sorted(found, key=lambda r: -r.preservation_rate)
