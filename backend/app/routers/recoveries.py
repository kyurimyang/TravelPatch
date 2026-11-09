from fastapi import APIRouter, HTTPException

from app.engine.candidate import UnsupportedEventError
from app.schemas.recovery import RecoveryInput, RecoveryResponse, RestoreRequest, RestoreResponse
from app.services.recovery_service import run_recovery, run_restore

router = APIRouter(prefix="/recoveries", tags=["recoveries"])


# Plain `def`s: the solve is CPU-bound, so FastAPI runs them in a worker thread instead of
# blocking the event loop.
@router.post("", response_model=RecoveryResponse)
def create_recovery(inp: RecoveryInput) -> RecoveryResponse:
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
