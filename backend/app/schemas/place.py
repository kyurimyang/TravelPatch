from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Place(BaseModel):
    """What we may keep of a Google place: the id, and its coordinates for a limited time.

    Names, opening hours and travel times are fetched when needed and never stored (see
    migration 0002). `lat`/`lng` None means "not cached (any more)", not "unknown place".
    """

    model_config = ConfigDict(frozen=True)

    place_id: str
    lat: float | None = None
    lng: float | None = None
    fetched_at: datetime | None = None


class PlaceOption(BaseModel):
    """A search hit as the browser sees it. No coordinates: the browser keeps a trip for longer
    than Google's 30-day limit, so lat/lng stay on the server. Name and address are for the
    picker only; the trip keeps the user's own title and the place_id."""

    model_config = ConfigDict(frozen=True)

    place_id: str
    name: str
    address: str | None


class PlaceSearchResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidates: tuple[PlaceOption, ...]  # Google's order; the user picks, never auto-selected
