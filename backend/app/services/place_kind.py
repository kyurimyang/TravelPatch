"""Whether a place is outdoors and how much walking it takes, from Google's place types
(decision 2026-11-27).

Rules on Google's own labels, not a guess (invariant 8): a type that settles it gives True or
False; anything else, or labels that disagree (a cafe in a park), stays None = unknown, which
the engine reads as "keep it, tell the user to check on site". The types are read per request
with the place's details and never stored (Google terms decision 2026-11-16).

Used for the day's own pieces (plan_builder) and for stand-in places (substitute_finder), so a
museum is "inside" in both.
"""

from app.schemas.enums import Category

INDOOR_TYPES = {
    "museum",
    "art_gallery",
    "aquarium",
    "shopping_mall",
    "department_store",
    "movie_theater",
    "library",
    "bowling_alley",
    "planetarium",
    "book_store",
    "restaurant",
    "cafe",
    "coffee_shop",
    "bar",
    "bakery",
    "spa",
}
INDOOR_SUFFIXES = ("_restaurant", "_cafe", "_bar", "_museum", "_store", "_shop")
OUTDOOR_TYPES = {
    "park",
    "garden",
    "botanical_garden",
    "zoo",
    "amusement_park",
    "beach",
    "hiking_area",
    "national_park",
    "campground",
    "plaza",
}
# Places that are mostly walking around (tiredness shortens them first).
WALKING_TYPES = OUTDOOR_TYPES | {"market", "shopping_mall", "department_store"}


def place_outdoor(types: tuple[str, ...]) -> bool | None:
    """True / False when Google's types say so, None when they do not (or disagree)."""
    outside = any(t in OUTDOOR_TYPES for t in types)
    inside = any(t in INDOOR_TYPES or t.endswith(INDOOR_SUFFIXES) for t in types)
    if outside == inside:
        return None
    return outside


def place_walking(types: tuple[str, ...], category: Category) -> bool | None:
    """True for a walk-around place, False for sitting down (a meal, a cafe), else None."""
    if category in (Category.MEAL, Category.CAFE):
        return False
    if any(t in WALKING_TYPES for t in types):
        return True
    return None
