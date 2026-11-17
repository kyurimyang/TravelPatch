import math
import time

from app.engine.conflict_detector import find_blockers
from app.engine.counterfactual import restore
from app.engine.recover import recover
from app.schemas.recovery import (
    RecoveryInput,
    RecoveryResponse,
    RecoveryResult,
    RestoreRequest,
    RestoreResponse,
)
from app.services.substitute_finder import needs_check_ids


def _elapsed_ms(start: float) -> int:
    return math.ceil((time.perf_counter() - start) * 1000)


def _mark_unknown_substitutes(inp: RecoveryInput, result: RecoveryResult) -> RecoveryResult:
    """A plan that goes to a substitute with unknown hours says "check on site" (invariant 8)."""
    unknown = needs_check_ids(inp)
    if not unknown:
        return result
    changes = tuple(
        c.model_copy(update={"needs_check": True}) if c.substitute_id in unknown else c
        for c in result.changes
    )
    return result.model_copy(update={"changes": changes})


def run_recovery(inp: RecoveryInput) -> RecoveryResponse:
    """Call the engine and do what the engine must not: read the clock.

    solver_ms is the time of the whole call (all strategies), copied onto every candidate;
    the engine itself leaves it 0. With no candidate, the blockers say why.
    """
    start = time.perf_counter()
    results = recover(inp)
    solver_ms = _elapsed_ms(start)
    candidates = tuple(
        _mark_unknown_substitutes(inp, r.model_copy(update={"solver_ms": solver_ms}))
        for r in results
    )
    blockers = () if candidates else tuple(find_blockers(inp))
    return RecoveryResponse(candidates=candidates, blockers=blockers, used_input=inp)


def run_restore(req: RestoreRequest) -> RestoreResponse:
    """ "What if I keep X?" for a candidate the user is looking at.

    The candidate is recomputed here from the input, never taken from the client, so the plan
    the counterfactual is measured against has been through the validator too.
    LookupError: the input has no candidate for that strategy. ValueError: X is not dropped in it.
    """
    start = time.perf_counter()
    base = next((r for r in recover(req.input) if r.strategy == req.strategy), None)
    if base is None:
        raise LookupError(f"no candidate for strategy: {req.strategy}")
    cf = restore(req.input, base, req.activity_id)
    if cf is not None:
        timed = _mark_unknown_substitutes(
            req.input, cf.result.model_copy(update={"solver_ms": _elapsed_ms(start)})
        )
        cf = cf.model_copy(update={"result": timed})
    return RestoreResponse(counterfactual=cf)
