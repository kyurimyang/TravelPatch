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


def hours_for_weekday(periods: tuple[OpeningPeriod, ...] | None, python_weekday: int) -> DayHours:
    """`python_weekday`: Monday=0..Sunday=6 (`date.weekday()`). Google counts Sunday as 0."""
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
    if len(windows) > 1:
        return UNKNOWN
    return DayHours("known", windows[0][0], windows[0][1])
