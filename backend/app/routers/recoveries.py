from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.engine.candidate import UnsupportedEventError
from app.llm.provider import LLMProvider
from app.routers.deps import get_places_client_optional, get_provider_optional
from app.schemas.recovery import (
    LockRequest,
    RecoveryInput,
    RecoveryResponse,
    RestoreRequest,
    RestoreResponse,
)
from app.services.lock import lock_in_place
from app.services.places_client import GooglePlacesClient
from app.services.recovery_service import run_recovery, run_restore
from app.services.substitute_finder import add_substitutes

router = APIRouter(prefix="/recoveries", tags=["recoveries"])


# Plain `def`s: the solve is CPU-bound, so FastAPI runs them in a worker thread instead of
# blocking the event loop.
@router.post("", response_model=RecoveryResponse)
def create_recovery(
    inp: RecoveryInput,
    provider: Annotated[LLMProvider | None, Depends(get_provider_optional)],
    places: Annotated[GooglePlacesClient | None, Depends(get_places_client_optional)],
) -> RecoveryResponse:
    # Step ⑦ before ⑧: a closure without substitutes gets searched ones (I/O stays out of the engine).
    if provider is not None and places is not None:
        inp = add_substitutes(inp, provider, places)
    try:
        return run_recovery(inp)
    except UnsupportedEventError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e


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
