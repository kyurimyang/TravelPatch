"""Rule-based step after the parser: `ParsedItinerary` (loose strings) -> `DraftItinerary`.

Pure and deterministic. It converts "HH:MM" to minutes since midnight, fills a missing end
time from a per-category default length (marked `duration_estimated`), and lists what the user
must check. It never reorders, drops or invents items, and it never guesses a missing start
time: that becomes an issue (invariant 8).
"""

import re

from app.llm.parser import ParsedDay, ParsedItem, ParsedItinerary
from app.schemas.itinerary import DraftDay, DraftIssue, DraftItem, DraftItinerary
from app.schemas.models import MINUTES_PER_DAY

# Draft values, shown to the user as estimates ("약 60분") and easy to change on the confirm screen.
DEFAULT_MINUTES: dict[str, int] = {
    "meal": 60,
    "sightseeing": 90,
    "shopping": 60,
    "cafe": 45,
    "transport": 30,
    "other": 60,
}

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def _minutes(text: str | None) -> int | None:
    """None for no time; raises ValueError for text that is not a clock time."""
    if text is None or not text.strip():
        return None
    match = _TIME_RE.match(text.strip())
    if match is None:
        raise ValueError(text)
    return int(match.group(1)) * 60 + int(match.group(2))


def _squash(text: str) -> str:
    return "".join(text.split()).casefold()


def _place_query(item: ParsedItem) -> str | None:
    """The model's place name, kept only if it is written in the line (title or note), spaces
    aside. Anything else is a guess and is dropped (invariants 4 and 8)."""
    query = (item.place_query or "").strip()
    if not query:
        return None
    written = _squash(item.title) + "\n" + _squash(item.note or "")
    return query if _squash(query) in written else None


def _convert_item(index: int, item: ParsedItem) -> tuple[DraftItem, list[DraftIssue]]:
    issues: list[DraftIssue] = []

    def read(raw: str | None, which: str) -> int | None:
        try:
            return _minutes(raw)
        except ValueError:
            issues.append(DraftIssue(code="BAD_TIME", item=index, detail=f"{which}={raw!r}"))
            return None

    start, end = read(item.start, "start"), read(item.end, "end")
    estimated = False
    if start is not None and end is None and not any(i.code == "BAD_TIME" for i in issues):
        end = start + DEFAULT_MINUTES[item.category]
        estimated = True
        if end > MINUTES_PER_DAY:
            issues.append(DraftIssue(code="OVER_MIDNIGHT", item=index, detail=f"end={end}"))
            end = MINUTES_PER_DAY
    elif start is None and end is not None:
        issues.append(DraftIssue(code="MISSING_START", item=index, detail=f"end={end}"))
    elif start is None and end is None and not issues:
        issues.append(DraftIssue(code="NO_TIME", item=index, detail=item.title))
    if start is not None and end is not None and end <= start:
        issues.append(DraftIssue(code="BAD_RANGE", item=index, detail=f"{start}-{end}"))

    reservation = None
    if item.reserved:
        if start is None:
            issues.append(DraftIssue(code="RESERVED_NO_TIME", item=index, detail=item.title))
        else:
            reservation = start
    draft = DraftItem(
        title=item.title,
        category=item.category,
        start=start,
        end=end,
        duration_estimated=estimated,
        reservation_time=reservation,
        note=item.note,
        place_query=_place_query(item),
        patch=item.patch,
    )
    return draft, issues


def _check_sequence(items: tuple[DraftItem, ...]) -> list[DraftIssue]:
    """Compare each placed item with the nearest placed item above it."""
    out: list[DraftIssue] = []
    prev: DraftItem | None = None
    for i, item in enumerate(items):
        if item.start is None:
            continue
        if prev is not None and prev.start is not None:
            if item.start < prev.start:
                out.append(DraftIssue(code="OUT_OF_ORDER", item=i, detail=item.title))
            elif prev.end is not None and item.start < prev.end:
                out.append(DraftIssue(code="OVERLAP", item=i, detail=item.title))
        prev = item
    return out


def _convert_day(day: ParsedDay) -> DraftDay:
    items: list[DraftItem] = []
    issues: list[DraftIssue] = []
    for index, parsed in enumerate(day.items):
        draft, found = _convert_item(index, parsed)
        items.append(draft)
        issues.extend(found)
    issues.extend(_check_sequence(tuple(items)))
    issues.sort(key=lambda i: (i.item, i.code))  # deterministic order for the UI and tests
    return DraftDay(day_label=day.day_label, items=tuple(items), issues=tuple(issues))


def build_draft(parsed: ParsedItinerary) -> DraftItinerary:
    return DraftItinerary(days=tuple(_convert_day(d) for d in parsed.days))
