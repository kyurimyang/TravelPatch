from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.routers.deps import get_places_client
from app.schemas.plan import BuiltPlan, PlanRequest
from app.services.places_client import GooglePlacesClient, PlacesError
from app.services.plan_builder import build_plan

router = APIRouter(prefix="/plans", tags=["plans"])


# Plain `def`: Google calls block, so FastAPI runs it in a worker thread.
@router.post("/build", response_model=BuiltPlan)
def build(
    req: PlanRequest, places: Annotated[GooglePlacesClient, Depends(get_places_client)]
) -> BuiltPlan:
    """One trip day (place_ids, times, tiers) -> engine input pieces. Nothing is stored."""
    try:
        return build_plan(req, places)
    except PlacesError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
