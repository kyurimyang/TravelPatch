from enum import StrEnum


class Tier(StrEnum):
    MUST = "must"
    NICE = "nice"
    OPTIONAL = "optional"

    @property
    def weight(self) -> int:
        return _TIER_WEIGHT[self]


_TIER_WEIGHT: dict[Tier, int] = {Tier.MUST: 5, Tier.NICE: 3, Tier.OPTIONAL: 1}


class Category(StrEnum):
    MEAL = "meal"
    SIGHTSEEING = "sightseeing"
    SHOPPING = "shopping"
    CAFE = "cafe"
    TRANSPORT = "transport"
    OTHER = "other"


class TravelMode(StrEnum):
    """How the traveler gets around. Only the service layer reads it (travel time estimates);
    the engine receives a finished travel table."""

    TRANSIT = "transit"  # walking + subway / bus
    WALK = "walk"
    CAR = "car"  # taxi or rental car


class TimeRigidity(StrEnum):
    RESERVED = "reserved"
    TIME_WINDOW = "time_window"
    FLEXIBLE = "flexible"


class Op(StrEnum):
    KEEP = "keep"
    MOVE = "move"
    SHRINK = "shrink"
    DROP = "drop"
    SUBSTITUTE = "substitute"
    EXTEND = "extend"
    ADD = "add"


class EventType(StrEnum):
    DELAY = "DELAY"
    WEATHER = "WEATHER"
    CLOSURE = "CLOSURE"
    FATIGUE = "FATIGUE"
    EXTEND = "EXTEND"
    RESERVATION_CHANGE = "RESERVATION_CHANGE"
    MUST_VISIT = "MUST_VISIT"
    # Queue at a place of the plan: that many minutes there before the activity itself starts
    # (decision 2026-11-26). Unlike EXTEND the piece can still be shortened, swapped or dropped.
    WAIT = "WAIT"


class Wish(StrEnum):
    """What the traveller would like for the rest of the day, said with or without an event
    ("실내에서 최대한 머무르고 싶어요"). Not a hard rule: see where each one is read."""

    INDOOR = "indoor"  # engine: D_outdoor in the cost (soft, decision 2026-11-26)
    LESS_WALKING = "less_walking"  # rules: becomes a FATIGUE event
    REST = "rest"  # rules: a FATIGUE event; service: the "relaxed" strategy comes first


class ReasonType(StrEnum):
    BINDING = "binding"
    VALUE = "value"
    COUNTERFACTUAL = "counterfactual"
