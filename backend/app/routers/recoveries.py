from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.engine.candidate import UnsupportedEventError
from app.llm.provider import LLMProvider
from app.routers.deps import (
    Caller,
    allow,
    get_caller,
    get_guest_quota,
    get_places_client_optional,
    get_provider_optional,
)
from app.schemas.recovery import (
    LockRequest,
    RecoveryRequest,
    RecoveryResponse,
    RestoreRequest,
    RestoreResponse,
)
from app.services.guest_quota import GuestQuota, Kind
from app.services.lock import lock_in_place
from app.services.places_client import GooglePlacesClient
from app.services.recovery_service import run_recovery, run_restore
from app.services.substitute_finder import (
    add_substitutes,
    add_substitutes_for,
    wants_substitutes,
)
from app.services.visited import VisitedError, apply_visited

router = APIRouter(prefix="/recoveries", tags=["recoveries"])

# Pieces a plan drops that get a search for a similar place nearby (one LLM call and one
# Google search each), the most valuable first. Small on purpose: it runs on every patch
# that drops something.
MAX_DROP_SEARCHES = 2


def _dropped_worth_a_search(inp, response: RecoveryResponse) -> list[str]:
    """Activities some candidate drops and that have no substitute yet, highest tier first."""
    weight = {p.activity_id: p.tier.weight for p in inp.preferences}
    has_sub = {s.replaces for s in inp.substitutes}
    dropped = {
        c.activity_id
        for r in response.candidates
        for c in r.changes
        if c.op == "drop" and c.activity_id not in has_sub and c.activity_id in weight
    }
    return sorted(dropped, key=lambda a: (-weight[a], a))[:MAX_DROP_SEARCHES]


# Plain `def`s: the solve is CPU-bound, so FastAPI runs them in a worker thread instead of
# blocking the event loop.
@router.post("", response_model=RecoveryResponse)
def create_recovery(
    req: RecoveryRequest,
    provider: Annotated[LLMProvider | None, Depends(get_provider_optional)],
    places: Annotated[GooglePlacesClient | None, Depends(get_places_client_optional)],
    caller: Annotated[Caller, Depends(get_caller)],
    quota: Annotated[GuestQuota, Depends(get_guest_quota)],
) -> RecoveryResponse:
    try:
        inp = apply_visited(req.plan(), req.visited)  # what is left of the day (limit 8)
    except VisitedError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    # Step ⑦ before ⑧: a closure without substitutes gets searched ones (I/O stays out of the engine).
    # A guest is charged only when that search happens; past the limit the engine still solves,
    # without searched substitutes (the same answer as a server with no keys).
    if (
        provider is not None
        and places is not None
        and wants_substitutes(inp)
        and allow(caller, Kind.LLM, quota)
        and allow(caller, Kind.PLACES, quota)
    ):
        inp = add_substitutes(inp, provider, places)
    try:
        response = run_recovery(inp)
    except UnsupportedEventError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e
    # A plan that drops a piece: look for a similar place nearby and solve again, so "instead of
    # dropping it, go here" can be offered (2026-11-24). Only kept when it changes something.
    targets = _dropped_worth_a_search(inp, response)
    if (
        targets
        and provider is not None
        and places is not None
        and allow(caller, Kind.LLM, quota)
        and allow(caller, Kind.PLACES, quota)
    ):
        richer = add_substitutes_for(inp, targets, provider, places)
        if richer is not inp:
            response = run_recovery(richer)
    return response


@router.post("/restore", response_model=RestoreResponse)
def restore_activity(req: RestoreRequest) -> RestoreResponse:
    try:
        return run_restore(req)
    # UnsupportedEventError is a ValueError, so it has to be caught first.
    except UnsupportedEventError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/lock", response_model=RecoveryResponse)
def lock_activities(req: LockRequest) -> RecoveryResponse:
    """Recompute with the given activities held in place. `used_input` in the answer carries the
    lock, so a later restore or lock builds on it."""
    try:
        locked = lock_in_place(req.input, req.activity_ids)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    try:
        return run_recovery(locked)
    except UnsupportedEventError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e
