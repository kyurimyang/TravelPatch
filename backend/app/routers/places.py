from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.routers.deps import get_places_client
from app.schemas.place import PlaceOption, PlaceSearchResponse
from app.services.places_client import GooglePlacesClient, PlacesError

router = APIRouter(prefix="/places", tags=["places"])


# Plain `def`: the Google call blocks, so FastAPI runs it in a worker thread.
@router.get("/search", response_model=PlaceSearchResponse)
def search(
    places: Annotated[GooglePlacesClient, Depends(get_places_client)],
    q: Annotated[str, Query(min_length=1, max_length=100)],
    city: Annotated[str | None, Query(max_length=60)] = None,
) -> PlaceSearchResponse:
    """Step ②: candidates for one itinerary line, for the user to pick (never auto-picked)."""
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="q is blank")
    if city and city.strip():
        query = f"{query} {city.strip()}"
    try:
        hits = places.search(query)
    except PlacesError as e:  # the message never holds the key (places_client)
        raise HTTPException(status_code=502, detail=str(e)) from e
    return PlaceSearchResponse(
        candidates=tuple(
            PlaceOption(place_id=h.place_id, name=h.name, address=h.address) for h in hits
        )
    )
