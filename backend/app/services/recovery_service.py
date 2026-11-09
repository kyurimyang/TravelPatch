import math
import time

from app.engine.conflict_detector import find_blockers
from app.engine.counterfactual import restore
from app.engine.recover import recover
from app.schemas.recovery import RecoveryInput, RecoveryResponse, RestoreRequest, RestoreResponse


def _elapsed_ms(start: float) -> int:
    return math.ceil((time.perf_counter() - start) * 1000)


def run_recovery(inp: RecoveryInput) -> RecoveryResponse:
    """Call the engine and do what the engine must not: read the clock.

    solver_ms is the time of the whole call (all strategies), copied onto every candidate;
    the engine itself leaves it 0. With no candidate, the blockers say why.
    """
    start = time.perf_counter()
    results = recover(inp)
    solver_ms = _elapsed_ms(start)
    candidates = tuple(r.model_copy(update={"solver_ms": solver_ms}) for r in results)
    blockers = () if candidates else tuple(find_blockers(inp))
    return RecoveryResponse(candidates=candidates, blockers=blockers)


def run_restore(req: RestoreRequest) -> RestoreResponse:
    """"What if I keep X?" for a candidate the user is looking at.

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
        timed = cf.result.model_copy(update={"solver_ms": _elapsed_ms(start)})
        cf = cf.model_copy(update={"result": timed})
    return RestoreResponse(counterfactual=cf)
