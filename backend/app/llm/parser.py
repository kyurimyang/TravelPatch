"""Step ①: pasted itinerary text -> loose `ParsedItinerary` (LLM call #1 of 3).

The LLM only copies what the text says. It never looks places up, never sets importance
(that is step ③) and never computes minutes: times stay "HH:MM" strings that a rule-based
step validates and converts afterwards (invariant 4). Unknown means null, not a guess
(invariant 8).
"""

from typing import Literal, get_args

from pydantic import BaseModel, Field

from app.llm.provider import LLMProvider

MAX_TEXT_CHARS = 8000  # a few days of notes; longer pasted text is refused before any LLM call

# Which patch picture the screen sticks on an item. Picture only: the engine never reads it.
# Language-free on purpose (the service is worldwide): the model judges what the place is.
PatchKind = Literal[
    "worship",
    "museum",
    "viewpoint",
    "bar",
    "market",
    "nature",
    "spa",
    "beach",
    "lodging",
    "theme_park",
    "venue",
    "mall",
]
PATCH_KINDS: tuple[str, ...] = get_args(PatchKind)

SYSTEM_PROMPT = """\
You turn a traveler's pasted itinerary (from a notepad, a chat or a spreadsheet) into a form.
Split it into days in the order written. For every place or activity give:
- title: the words used in the text, not translated or "fixed".
- start / end: 24-hour "HH:MM" exactly as written ("오후 3시" -> "15:00"). If the text gives
  only a start time, leave end null. If it gives no time, leave both null. Never invent a time.
- category: meal, sightseeing, shopping, cafe, transport or other. Use other when unclear.
- patch: what kind of place it is, judged from the name in any language, or null when the line
  is none of these or you are not sure: worship (temple, shrine, church, mosque), museum
  (museum, gallery, aquarium), viewpoint (observation deck, tower, night view), bar (bar, pub,
  izakaya), market (market, night market), nature (park, garden, mountain, lake), spa (hot
  spring, spa, sauna), beach, lodging (hotel, check-in), theme_park (amusement park, theme park,
  zoo), venue (concert hall, theater, stadium, show), mall (shopping mall, department store).
- reserved: true only if the text says it is booked or reserved ("예약", "reservation").
- note: anything else written on that line (price, address, reminder), or null.
- place_query: only the name of the place to look up on a map, copied from the line as written,
  without activity words ("오모테산도 산책" -> "오모테산도", "이치란 라멘 점심" -> "이치란 라멘").
  null when the line names no particular place ("점심 - 스시", "쇼핑"). Never add a name that is
  not written.

Rules:
- Do not add, merge, reorder or drop items. One line of the text is at most one item.
- day_label is the heading the text uses for the day ("1일차", "Day 2", "10/8"), or null.
- If a day has no heading, still make a day for it, with day_label null.
"""


class ParsedItem(BaseModel):
    title: str
    start: str | None = Field(description="HH:MM as written, or null")
    end: str | None = Field(description="HH:MM as written, or null")
    category: Literal["meal", "sightseeing", "shopping", "cafe", "transport", "other"]
    reserved: bool
    note: str | None
    place_query: str | None = Field(description="place name as written in the line, or null")
    patch: PatchKind | None = Field(description="kind of place, or null")


class ParsedDay(BaseModel):
    day_label: str | None
    items: list[ParsedItem]


class ParsedItinerary(BaseModel):
    days: list[ParsedDay]


class TextTooLongError(ValueError):
    pass


def parse_itinerary(provider: LLMProvider, text: str) -> ParsedItinerary:
    """Raises `LLMOutputError` when the provider fails twice; the caller then asks the user to
    enter the plan by hand."""
    cleaned = text.strip()
    if len(cleaned) > MAX_TEXT_CHARS:
        raise TextTooLongError(f"itinerary text is {len(cleaned)} chars, max {MAX_TEXT_CHARS}")
    return provider.complete_json(system=SYSTEM_PROMPT, user=cleaned, schema=ParsedItinerary)
