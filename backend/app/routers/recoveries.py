from fastapi import APIRouter

from app.schemas.recovery import RecoveryInput, RecoveryResponse
from app.services.recovery_service import run_recovery

router = APIRouter(prefix="/recoveries", tags=["recoveries"])


# A plain `def`: the solve is CPU-bound, so FastAPI runs it in a worker thread instead of
# blocking the event loop.
@router.post("", response_model=RecoveryResponse)
def create_recovery(inp: RecoveryInput) -> RecoveryResponse:
    return run_recovery(inp)
