from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.routers.deps import charged_places, get_routes_client_optional
from app.schemas.plan import BuiltPlan, PlanRequest
from app.services.add_place import AddPlaceRequest, AddPlaceResponse, add_place
from app.services.places_client import GooglePlacesClient, PlacesError
from app.services.plan_builder import build_plan
from app.services.routes_client import GoogleRoutesClient

router = APIRouter(prefix="/plans", tags=["plans"])


# Plain `def`: Google calls block, so FastAPI runs it in a worker thread.
@router.post("/build", response_model=BuiltPlan)
def build(
    req: PlanRequest,
    places: Annotated[GooglePlacesClient, Depends(charged_places)],
    routes: Annotated[GoogleRoutesClient | None, Depends(get_routes_client_optional)],
) -> BuiltPlan:
    """One trip day (place_ids, times, tiers) -> engine input pieces. Nothing is stored.
    Real travel minutes from Google Routes when a key is set, estimates otherwise. The Routes
    call is part of this one counted call (same daily limit as Places)."""
    try:
        return build_plan(req, places, routes)
    except PlacesError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/add-place", response_model=AddPlaceResponse)
def add_place_to_day(
    req: AddPlaceRequest, places: Annotated[GooglePlacesClient, Depends(charged_places)]
) -> AddPlaceResponse:
    """ "꼭 가고 싶은 곳": a picked place -> the MUST_VISIT event and the day's travel table with it,
    ready for POST /recoveries. Nothing is stored."""
    try:
        return add_place(req, places)
    except PlacesError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
