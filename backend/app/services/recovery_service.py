import math
import time

from app.engine.conflict_detector import find_blockers
from app.engine.recover import recover
from app.schemas.recovery import RecoveryInput, RecoveryResponse


def run_recovery(inp: RecoveryInput) -> RecoveryResponse:
    """Call the engine and do what the engine must not: read the clock.

    solver_ms is the time of the whole call (all strategies), copied onto every candidate;
    the engine itself leaves it 0. With no candidate, the blockers say why.
    """
    start = time.perf_counter()
    results = recover(inp)
    solver_ms = math.ceil((time.perf_counter() - start) * 1000)
    candidates = tuple(r.model_copy(update={"solver_ms": solver_ms}) for r in results)
    blockers = () if candidates else tuple(find_blockers(inp))
    return RecoveryResponse(candidates=candidates, blockers=blockers)
