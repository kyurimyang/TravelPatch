from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.routers.deps import charged_places
from app.schemas.place import PlaceOption, PlaceSearchResponse
from app.services.places_client import GooglePlacesClient, PlacesError
from app.services.travel_estimate import haversine_km

router = APIRouter(prefix="/places", tags=["places"])

# Draft values (decision 2026-11-18). The bias prefers the branch near the hotel without hiding
# places further out (a day trip is still found); FAR_KM only marks a hit for a second look.
BIAS_RADIUS_M = 10_000.0
FAR_KM = 20.0


def _hotel_point(places: GooglePlacesClient, place_id: str | None) -> tuple[float, float] | None:
    """The hotel's coordinates, or None when not given or Google cannot say. A failed lookup
    only loses the bias: the search itself still runs."""
    if not place_id:
        return None
    try:
        hotel = places.details(place_id)
    except PlacesError:
        return None
    return hotel.lat, hotel.lng


# Plain `def`: the Google call blocks, so FastAPI runs it in a worker thread.
@router.get("/search", response_model=PlaceSearchResponse)
def search(
    places: Annotated[GooglePlacesClient, Depends(charged_places)],
    q: Annotated[str, Query(min_length=1, max_length=100)],
    city: Annotated[str | None, Query(max_length=60)] = None,
    near: Annotated[str | None, Query(max_length=300, description="hotel place_id")] = None,
) -> PlaceSearchResponse:
    """Step ②: candidates for one itinerary line, nearest to the hotel first when it is known."""
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="q is blank")
    if city and city.strip():
        query = f"{query} {city.strip()}"
    hotel = _hotel_point(places, near)
    try:
        hits = places.search(query, near=hotel, radius_m=BIAS_RADIUS_M)
    except PlacesError as e:  # the message never holds the key (places_client)
        raise HTTPException(status_code=502, detail=str(e)) from e
    return PlaceSearchResponse(
        candidates=tuple(
            PlaceOption(
                place_id=h.place_id,
                name=h.name,
                address=h.address,
                far=None if hotel is None else haversine_km(hotel, (h.lat, h.lng)) > FAR_KM,
            )
            for h in hits
        )
    )
