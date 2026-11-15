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
