from pydantic import Field

from app.schemas.enums import Category
from app.schemas.models import _Frozen


class Weights(_Frozen):
    w_drop: float = 1.0
    w_shrink: float = 0.6
    w_sub: float = 0.8
    w_order: float = 0.3
    w_time: float = 0.05
    w_move: float = 0.2
    w_intent: float = 1.0
    # Cost per changed activity (any op but keep). 0.2 sits in the 0.1-0.3 plateau of the
    # sweep over scenarios A, B, D, E; re-check on the 50-scenario evaluation set.
    w_changed: float = 0.2
    # Extra multiplier on w_drop for some categories, e.g. ((SIGHTSEEING, 2.0),).
    category_drop_factor: tuple[tuple[Category, float], ...] = ()

    def drop_factor(self, category: Category) -> float:
        return dict(self.category_drop_factor).get(category, 1.0)


class Strategy(_Frozen):
    name: str
    weights: Weights
    # Hard constraint: extra slack between activities, on top of travel time.
    min_buffer: int = Field(default=0, ge=0)
    # Hard constraint: arrive this many minutes before every booking (on top of travel time).
    reservation_buffer: int = Field(default=0, ge=0)
    # Hard constraint: activities of these categories are never dropped.
    no_drop_categories: tuple[Category, ...] = ()


# Initial draft values from CLAUDE.md; to be tuned by experiments.
DEFAULT_WEIGHTS = Weights()

# Hard constraint for every strategy (review 2026-11-19, A3): a meal starts within this many
# minutes of its planned start, either way. Not a weight: lunch at 17:00 is wrong, not costly.
# Shared by the solver and the validator, which each enforce it on their own (invariant 3).
MEAL_WINDOW_MINUTES = 90

# Draft value for the "reservation" strategy: minutes early at every booking.
RESERVATION_BUFFER = 15

# The only place strategies are defined. Order matters: the first one is the default.
STRATEGIES: tuple[Strategy, ...] = (
    Strategy(name="balanced", weights=DEFAULT_WEIGHTS),
    Strategy(
        name="sightseeing",
        weights=Weights(category_drop_factor=((Category.SIGHTSEEING, 2.0),)),
    ),
    Strategy(name="low_travel", weights=Weights(w_move=0.2 * 4, w_order=0.1)),
    Strategy(name="relaxed", weights=Weights(w_drop=0.7), min_buffer=20),
    # CLAUDE.md 6, added 2026-11-22. Rules, not weights: a hard "no", checked by the validator.
    Strategy(name="food", weights=DEFAULT_WEIGHTS, no_drop_categories=(Category.MEAL,)),
    Strategy(name="reservation", weights=DEFAULT_WEIGHTS, reservation_buffer=RESERVATION_BUFFER),
)

# How many distinct candidates the user is shown (CLAUDE.md 6: 2-3), balanced first.
SHOWN_CANDIDATES = 3
