"""Opening hours of one weekday as the engine wants them: `open_at`/`close_at` in minutes.

Pure. The engine takes a single window per activity, so a day with a lunch break (two
windows) cannot be expressed. It is reported as "unknown" instead of being flattened into one
long window, which would let the solver schedule a visit during the break (invariant 8).
"""

from dataclasses import dataclass
from typing import Literal

from app.schemas.models import MINUTES_PER_DAY
from app.services.places_client import OpeningPeriod


@dataclass(frozen=True)
class DayHours:
    status: Literal["known", "closed", "unknown"]
    open_at: int | None = None
    close_at: int | None = None


UNKNOWN = DayHours("unknown")


def hours_for_weekday(
    periods: tuple[OpeningPeriod, ...] | None,
    python_weekday: int,
    prefer: tuple[int, int] | None = None,
) -> DayHours:
    """`python_weekday`: Monday=0..Sunday=6 (`date.weekday()`). Google counts Sunday as 0.

    Several windows in a day (a lunch break, or last night's hours running past midnight) are
    never merged. With `prefer` (the slot the visit is meant for), the one real window that
    overlaps it most is used: the visit then stays inside hours the place is truly open.
    Without it, several windows stay "unknown".
    """
    if periods is None:
        return UNKNOWN
    day = (python_weekday + 1) % 7
    windows: list[tuple[int, int]] = []
    for p in periods:
        if p.close_day is None or p.close_minute is None:  # open around the clock
            windows.append((0, MINUTES_PER_DAY))
        elif p.open_day == day:
            same_day = p.close_day == day and p.close_minute > p.open_minute
            windows.append((p.open_minute, p.close_minute if same_day else MINUTES_PER_DAY))
        elif p.close_day == day:  # opened the evening before and spills into this morning
            windows.append((0, p.close_minute))
    windows = sorted(set(windows))
    if not windows:
        return DayHours("closed")
    if len(windows) == 1:
        return DayHours("known", windows[0][0], windows[0][1])
    if prefer is None:
        return UNKNOWN

    def overlap(w: tuple[int, int]) -> int:
        return max(0, min(w[1], prefer[1]) - max(w[0], prefer[0]))

    # Most overlap first; ties go to the earlier window (sorted), so the choice is deterministic.
    best = max(windows, key=overlap)
    if overlap(best) == 0:
        return UNKNOWN  # no window near the slot: let the user check rather than guess
    return DayHours("known", best[0], best[1])
