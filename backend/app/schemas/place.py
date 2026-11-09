from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class Place(BaseModel):
    """A Google place as cached in the `places` table."""

    model_config = ConfigDict(frozen=True)

    place_id: str
    name: str
    lat: float
    lng: float
    # None means "unknown", not "always open" (invariant 8): callers must flag needs_check.
    opening_hours: dict[str, Any] | None = None
    fetched_at: datetime | None = None
