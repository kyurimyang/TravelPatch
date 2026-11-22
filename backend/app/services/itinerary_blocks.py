"""Rule step 2a: the parser's block roles -> the day's shape (pure, deterministic).

The parser labels every block activity / transport / lodging / airport (LLM). This module only
reads those labels and the written times; it decides nothing from world knowledge:
- airport blocks at the day's start / end -> the arrival / departure flight,
- transport / lodging blocks at the day's end -> the time the day ends at the hotel,
- transport blocks elsewhere -> legs between two items (the engine computes travel itself,
  so a leg is never an item),
- everything else stays an item, in the order written.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from app.llm.parser import ParsedItem
from app.schemas.itinerary import DraftFlight, DraftLeg

# Words that mark a transport block's destination as a hotel ("신주쿠 호텔 복귀").
HOTEL_WORD = re.compile(r"호텔|숙소|hotel|hostel|ホテル|旅館", re.IGNORECASE)

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def minutes_or_none(text: str | None) -> int | None:
    """Minutes since midnight, or None for no time or text that is not a clock time."""
    match = _TIME_RE.match((text or "").strip())
    return None if match is None else int(match.group(1)) * 60 + int(match.group(2))


def squash(text: str) -> str:
    return "".join(text.split()).casefold()


def find_hotel_query(days: list[list[ParsedItem]]) -> str | None:
    """The hotel as written: the place lodging blocks and hotel-bound transport blocks name
    most often. A tie goes to the name written first (deterministic)."""
    counts: Counter[str] = Counter()
    first: dict[str, tuple[int, str]] = {}
    for item in (it for day in days for it in day):
        query = (item.place_query or "").strip()
        if not query:
            continue
        if item.role == "lodging" or (item.role == "transport" and HOTEL_WORD.search(query)):
            key = squash(query)
            counts[key] += 1
            first.setdefault(key, (len(first), query))
    if not counts:
        return None
    best = max(counts, key=lambda k: (counts[k], -first[k][0]))
    return first[best][1]


def _goes_to_hotel(item: ParsedItem, hotel_query: str | None) -> bool:
    query = (item.place_query or "").strip()
    if not query:
        return False
    if hotel_query and squash(hotel_query) == squash(query):
        return True
    return bool(HOTEL_WORD.search(query))


@dataclass
class DayShape:
    items: list[ParsedItem] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)  # "activity" | "lodging" | "airport"
    legs: list[DraftLeg] = field(default_factory=list)
    arrival: DraftFlight | None = None
    departure: DraftFlight | None = None
    end_time: int | None = None


def _leg(item: ParsedItem, after: int | None, before: int | None) -> DraftLeg:
    return DraftLeg(
        after=after,
        before=before,
        start=minutes_or_none(item.start),
        end=minutes_or_none(item.end),
        title=item.title,
        note=item.note,
    )


def written_query(block: ParsedItem) -> str | None:
    """The model's place name, kept only if it is written in the block (title or note), spaces
    aside. Anything else is a guess and is dropped (invariants 4 and 8)."""
    query = (block.place_query or "").strip()
    if not query:
        return None
    written = squash(block.title) + "\n" + squash(block.note or "")
    return query if squash(query) in written else None


def _airport_query(blocks: list[ParsedItem], fallback: ParsedItem | None) -> str | None:
    for block in [*blocks, *([fallback] if fallback else [])]:
        query = written_query(block)
        if query:
            return query
    return None


def _arrival(blocks: list[ParsedItem]) -> DraftFlight | None:
    landing = minutes_or_none(blocks[0].start)
    if landing is None:
        return None
    ready = minutes_or_none(blocks[-1].end)
    return DraftFlight(
        airport_query=_airport_query(blocks, None),
        time=landing,
        buffer_minutes=None if ready is None or ready < landing else ready - landing,
        time_written=True,
        absorbed=tuple(b.title for b in blocks),
    )


def _departure(blocks: list[ParsedItem], before: ParsedItem | None) -> DraftFlight | None:
    at_airport = minutes_or_none(blocks[0].start)
    last = blocks[-1]
    # A last block with only a start ("14:00 출국편") is the take-off itself. A last block with
    # a range ("12:00~12:40 탑승 대기") ends before a take-off that is not written.
    last_end = minutes_or_none(last.end)
    take_off, written = (
        (minutes_or_none(last.start), True) if last_end is None else (last_end, False)
    )
    if at_airport is None or take_off is None or take_off < at_airport:
        return None
    hop = before if before is not None and before.role == "transport" else None
    return DraftFlight(
        airport_query=_airport_query(blocks, hop),
        time=take_off,
        buffer_minutes=take_off - at_airport,
        time_written=written,
        absorbed=tuple(b.title for b in blocks),
    )


def shape_day(blocks: list[ParsedItem], hotel_query: str | None) -> DayShape:
    shape = DayShape()
    lo, hi = 0, len(blocks)

    while lo < hi and blocks[lo].role == "airport":
        lo += 1
    if lo:
        shape.arrival = _arrival(blocks[:lo])
        if shape.arrival is None:
            lo = 0  # no landing time: keep the blocks as items for the user to fix

    cut = hi
    while cut > lo and blocks[cut - 1].role == "airport":
        cut -= 1
    if cut < hi:
        shape.departure = _departure(blocks[cut:hi], blocks[cut - 1] if cut > lo else None)
        if shape.departure is not None:
            hi = cut

    # The tail: transport blocks to the end point, plus (without a flight) lodging blocks
    # back at the hotel. Their last time is when the day ends there.
    tail_roles = ("transport",) if shape.departure else ("transport", "lodging")
    cut = hi
    while cut > lo and blocks[cut - 1].role in tail_roles:
        cut -= 1
    tail, hi = blocks[cut:hi], cut
    if tail and shape.departure is None:
        ends = [minutes_or_none(b.end) or minutes_or_none(b.start) for b in tail]
        shape.end_time = max((m for m in ends if m is not None), default=None)

    pending: list[ParsedItem] = []  # transport blocks waiting for the next item
    for block in blocks[lo:hi]:
        role = block.role
        if role == "transport" and _goes_to_hotel(block, hotel_query):
            role = "lodging"  # going to the hotel mid-day is a stop there ("짐 보관")
        if role == "transport":
            pending.append(block)
            continue
        after = len(shape.items) - 1 if shape.items else None
        shape.items.append(block)
        shape.roles.append(role)
        shape.legs.extend(_leg(p, after, len(shape.items) - 1) for p in pending)
        pending = []

    last = len(shape.items) - 1 if shape.items else None
    shape.legs.extend(_leg(p, last, None) for p in pending)
    shape.legs.extend(_leg(b, last, None) for b in tail if b.role == "transport")
    return shape
