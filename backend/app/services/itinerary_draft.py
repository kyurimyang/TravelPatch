"""Rule-based step after the parser: `ParsedItinerary` (loose strings) -> `DraftItinerary`.

Pure and deterministic. It converts "HH:MM" to minutes since midnight, fills a missing end
time from a per-category default length (marked `duration_estimated`), and lists what the user
must check. It never reorders or invents items, and it never guesses a missing start time: that
becomes an issue (invariant 8). Transport, hotel and airport blocks are turned into legs, the
day's end and the flights by `itinerary_blocks` (step 2a), not dropped.

Given the pasted text, it also checks the model's times against it: an end the model left out
is restored when the text writes that start as a range ("13:00~16:00").
"""

import re

from app.llm.parser import ParsedDay, ParsedItem, ParsedItinerary
from app.schemas.itinerary import DraftDay, DraftIssue, DraftItem, DraftItinerary
from app.schemas.models import MINUTES_PER_DAY
from app.services.itinerary_blocks import find_hotel_query, shape_day
from app.services.itinerary_places import PlaceRef, resolve_places

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
# "13:00~16:00", "9:00 - 9:50", "10:00–11:00" anywhere in a line of the pasted text.
_RANGE_RE = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})\s*[~\-–—]\s*(\d{1,2}):(\d{2})(?!\d)")
# A line that starts with a single time ("16:20", "- 18:30 출발"): a point, not a range.
_POINT_LINE_RE = re.compile(r"^[^\w]*(\d{1,2}):(\d{2})(?!\d)")
# A remark, not a plan item: "※ 지연되면 한 곳만 방문", "* 입장권 확인", "참고: ...".
_REMARK_RE = re.compile(r"^\s*(?:※|\*|＊|참고|주의|note\b|nb\b)", re.IGNORECASE)
# A leading label that only names the category: "점심 식사: Fumotoya" -> "Fumotoya".
_LABEL_RE = re.compile(r"^[^\W\d][^:：\d]{0,14}[:：]\s*(\S.*)$")


def _minutes(text: str | None) -> int | None:
    """None for no time; raises ValueError for text that is not a clock time."""
    if text is None or not text.strip():
        return None
    match = _TIME_RE.match(text.strip())
    if match is None:
        raise ValueError(text)
    return int(match.group(1)) * 60 + int(match.group(2))


def written_ranges(text: str) -> list[tuple[str, str]]:
    """Every time range written in the text, in order, as zero-padded ("HH:MM", "HH:MM")."""
    return [
        (f"{int(h1):02d}:{m1}", f"{int(h2):02d}:{m2}") for h1, m1, h2, m2 in _RANGE_RE.findall(text)
    ]


TimeLine = tuple[str, str | None, str, str]  # (start, end or None, squashed line, line as written)


def written_time_lines(text: str) -> list[TimeLine]:
    """`written_times`, each with the line it is written on (squashed, and as written), so an
    item the model returned without a time can be found by its title, and a line no item
    covers can be shown to the user."""
    out: list[TimeLine] = []
    for line in text.splitlines():
        ranges = written_ranges(line)
        if ranges:
            out.extend((start, end, _squash(line), line.strip()) for start, end in ranges)
        else:
            point = _POINT_LINE_RE.match(line)
            if point is not None:
                start = f"{int(point.group(1)):02d}:{point.group(2)}"
                out.append((start, None, _squash(line), line.strip()))
    return out


def written_times(text: str) -> list[tuple[str, str | None]]:
    """Every time range in the text, plus every line that is a single time ("16:20"), in order.
    A single time has no end: "16:20 도착" must not take the "16:20~17:20" written under it."""
    return [(start, end) for start, end, _, _ in written_time_lines(text)]


def unread_lines(parsed: ParsedItinerary, text: str) -> list[str]:
    """The text's time lines that no item covers, as written, in order, after the times the model
    left out are taken back (`_align`). Language-free: it matches times, not words. Exact, not a
    share: a single dropped line counts, and it is the same answer every time (2026-11-28: the
    Busan paste lost a different line on each live run, each under the old 80% bar)."""
    lines = written_time_lines(text)
    _, used = _align([list(d.items) for d in parsed.days], lines)
    return [lines[i][3] for i in range(len(lines)) if i not in used]


def read_count(parsed: ParsedItinerary, text: str) -> tuple[int, int]:
    """(time lines some item covers, time lines written in the text)."""
    written = len(written_time_lines(text))
    return written - len(unread_lines(parsed, text)), written


def reads_short(parsed: ParsedItinerary, text: str) -> bool:
    """Some time line in the text came back as no item: ask again (the router does)."""
    return bool(unread_lines(parsed, text))


def _with_written_times(
    days: list[list[ParsedItem]], ranges: list[TimeLine]
) -> list[list[ParsedItem]]:
    return _align(days, ranges)[0]


def _align(
    days: list[list[ParsedItem]], ranges: list[TimeLine]
) -> tuple[list[list[ParsedItem]], set[int]]:
    """Restore times the model left out. Blocks come in the order written, so each start is
    matched with the next time line in the text that starts there (a cursor that only moves
    on): "13:00" on day 2 never takes day 1's "13:00~14:00", and a block written as a single
    time keeps no end.

    A block that came back with no time at all takes the time of the next unread time line, but
    only when its title is written on that very line: "20:00~ · 숙소 이동 및 휴식" read without
    its 20:00 (live test 2026-11-28, Busan) left day 1 with no end at the hotel. Only the next
    line, so a short untimed "쇼핑" never takes a later "14:00-16:00 아키하바라 쇼핑". The time
    is the one written (invariant 8); any other untimed block stays untimed."""
    cursor = 0
    used: set[int] = set()  # indexes into `ranges` some item took
    out: list[list[ParsedItem]] = []
    for day in days:
        fixed: list[ParsedItem] = []
        for item in day:
            title = _squash(item.title)
            if not (item.start or "").strip() and not (item.end or "").strip() and title:
                if cursor < len(ranges) and title in ranges[cursor][2]:
                    start, end = ranges[cursor][0], ranges[cursor][1]
                    used.add(cursor)
                    cursor += 1
                    item = item.model_copy(update={"start": start, "end": end})
                fixed.append(item)
                continue
            match = _TIME_RE.match((item.start or "").strip())
            if match is not None:
                start = f"{int(match.group(1)):02d}:{match.group(2)}"
                at = next((i for i in range(cursor, len(ranges)) if ranges[i][0] == start), None)
                if at is not None:
                    used.add(at)
                    cursor = at + 1
                    if not item.end and ranges[at][1] is not None:
                        item = item.model_copy(update={"end": ranges[at][1]})
            fixed.append(item)
        out.append(fixed)
    return out, used


def _title(raw: str) -> str:
    match = _LABEL_RE.match(raw.strip())
    return match.group(1).strip() if match else raw


def _squash(text: str) -> str:
    return "".join(text.split()).casefold()


def _convert_item(
    index: int, item: ParsedItem, role: str, place: PlaceRef
) -> tuple[DraftItem, list[DraftIssue]]:
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
    elif item.patch == "venue" and start is not None:
        # A show starts when it starts, booked or not: the engine moved a Broadway musical from
        # 19:30 to 19:15 (user test 2026-11-28). Held like a reservation (invariant 7); the
        # start is the one written, so nothing is guessed.
        reservation = start
    draft = DraftItem(
        title=_title(item.title),
        category=item.category,
        role=role,
        start=start,
        end=end,
        duration_estimated=estimated,
        reservation_time=reservation,
        note=item.note,
        place_source=place.source,
        place_of=place.of,
        place_query=place.query,
        address=place.address,
        spot=(item.spot or "").strip() or None,
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


def _convert_day(
    blocks: list[ParsedItem], day: ParsedDay, hotel: str | None, text: str | None
) -> DraftDay:
    shape = shape_day(blocks, hotel)
    places = resolve_places(shape, day, text)
    items: list[DraftItem] = []
    issues: list[DraftIssue] = []
    rows = zip(shape.items, shape.roles, places, strict=True)
    for index, (parsed, role, place) in enumerate(rows):
        draft, found = _convert_item(index, parsed, role, place)
        items.append(draft)
        issues.extend(found)
    issues.extend(_check_sequence(tuple(items)))
    issues.sort(key=lambda i: (i.item, i.code))  # deterministic order for the UI and tests
    return DraftDay(
        day_label=day.day_label,
        theme=day.theme,
        items=tuple(items),
        legs=tuple(shape.legs),
        arrival=shape.arrival,
        departure=shape.departure,
        end_time=shape.end_time,
        issues=tuple(issues),
    )


def _fold_remarks(day: list[ParsedItem]) -> list[ParsedItem]:
    """A remark line with no time ("※ 지연되면 한 곳만") goes into the note of the place above it
    instead of standing as an item: as an item it had no time and the user had to delete it on
    Confirm (the Prague paste, 2026-11-23). Nothing is lost: the words stay, as a note. A remark
    above every place stays an item."""
    out: list[ParsedItem] = []
    for item in day:
        remark = not (item.start or "").strip() and not (item.end or "").strip()
        target = next((i for i in range(len(out) - 1, -1, -1) if out[i].role == "activity"), None)
        if remark and _REMARK_RE.match(item.title) and target is not None:
            prev = out[target]
            note = f"{prev.note}\n{item.title}" if prev.note else item.title
            out[target] = prev.model_copy(update={"note": note})
        else:
            out.append(item)
    return out


def build_draft(parsed: ParsedItinerary, text: str | None = None) -> DraftItinerary:
    """`text` is the pasted text the parser read; with it, times are checked against it."""
    days = [_fold_remarks(list(d.items)) for d in parsed.days]
    if text:
        days = _with_written_times(days, written_time_lines(text))
    hotel = find_hotel_query(days)
    if hotel is not None and text is not None and _squash(hotel) not in _squash(text):
        hotel = None  # not written: a guess (invariant 8)
    return DraftItinerary(
        hotel_query=hotel,
        days=tuple(_convert_day(b, d, hotel, text) for b, d in zip(days, parsed.days, strict=True)),
    )
