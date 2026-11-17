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


class ReasonType(StrEnum):
    BINDING = "binding"
    VALUE = "value"
    COUNTERFACTUAL = "counterfactual"
