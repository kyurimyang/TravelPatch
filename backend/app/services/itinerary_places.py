"""Rule step 2b: where each item of a shaped day is (pure, deterministic).

The parser copies names from the block (place_query, address, within). This module checks that
each one is written, then decides from the day's order alone:
1. a lodging item is at the hotel;
2. a written address is searched with the name (the surest match);
3. `within` a place an earlier item already is (no leg in between) -> the same place: one pin
   for a day inside a theme park, not one per restaurant;
4. a written name is searched;
5. no name and no leg since the item before -> the same place as that item;
6. otherwise nothing: the user picks. Never a search by the title (invariant 8).
"""

import re
from dataclasses import dataclass

from app.llm.parser import ParsedDay, ParsedItem
from app.services.itinerary_blocks import DayShape, squash, written_query


@dataclass(frozen=True)
class PlaceRef:
    source: str  # "written" | "venue" | "previous" | "hotel" | "none"
    of: int | None = None
    query: str | None = None
    address: str | None = None


# A leading label word and a colon ("주소:", "Address:", "住所："), never digits or commas.
_ADDRESS_LABEL_RE = re.compile(r"^[^\W\d][^:：\d,]{0,14}[:：]\s*")

HOTEL = PlaceRef("hotel")
NONE = PlaceRef("none")


def _written_address(block: ParsedItem, text: str | None) -> str | None:
    # The model sometimes copies the line's label too ("주소: Dlouhá 33"): drop it.
    address = _ADDRESS_LABEL_RE.sub("", (block.address or "").strip())
    if not address:
        return None
    if text is not None and squash(address) not in squash(text):
        return None
    return address


def _day_words(day: ParsedDay) -> str:
    """Everything written for the day, to check a `within` name against."""
    parts = [day.theme or "", day.day_label or ""]
    for block in day.items:
        parts += [block.title, block.note or "", block.spot or "", block.address or ""]
    return squash("\n".join(parts))


def _root(refs: list[PlaceRef], j: int) -> PlaceRef:
    """The place item j stands on: itself, or the item it shares a place with."""
    ref = refs[j]
    if ref.source in ("hotel", "none"):
        return ref
    if ref.source in ("venue", "previous") and ref.of is not None:
        return PlaceRef("previous", of=ref.of)
    return PlaceRef("previous", of=j)


def resolve_places(shape: DayShape, day: ParsedDay, text: str | None) -> list[PlaceRef]:
    legs_after = {leg.after for leg in shape.legs}
    leaves_start = None in legs_after  # a leg before the first item: the day starts elsewhere

    def leg_between(j: int, i: int) -> bool:
        return any(k in legs_after for k in range(j, i))

    words = _day_words(day)
    refs: list[PlaceRef] = []
    for i, (block, role) in enumerate(zip(shape.items, shape.roles, strict=True)):
        query = written_query(block)
        address = _written_address(block, text)
        within = (block.within or "").strip()
        within = within if within and squash(within) in words else ""

        if role == "lodging":
            ref = HOTEL
        elif address:
            ref = PlaceRef("written", query=query, address=address)
        elif within:
            ref = _inside(refs, shape.items, i, within, leg_between)
            if ref is None:
                ref = (
                    PlaceRef("written", query=query)
                    if query
                    else PlaceRef("venue", query=within)  # no item for it yet: search it
                )
        elif query:
            ref = PlaceRef("written", query=query)
        elif i > 0 and not leg_between(i - 1, i):
            ref = _root(refs, i - 1)
        elif i == 0 and shape.arrival is None and not leaves_start:
            ref = HOTEL  # the day starts at the hotel and nothing moved it yet
        else:
            ref = NONE
        refs.append(ref)
    return refs


def _inside(refs, items, i, within, leg_between) -> PlaceRef | None:
    """The nearest earlier item, with no leg in between, whose place is `within`."""
    key = squash(within)
    for j in range(i - 1, -1, -1):
        if leg_between(j, i):
            return None
        name = squash(items[j].title) + "\n" + squash(refs[j].query or "")
        if key in name:
            root = _root(refs, j)
            return HOTEL if root.source == "hotel" else PlaceRef("venue", of=root.of)
    return None
