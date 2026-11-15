"""Step ①: pasted itinerary text -> loose `ParsedItinerary` (LLM call #1 of 3).

The LLM only copies what the text says. It never looks places up, never sets importance
(that is step ③) and never computes minutes: times stay "HH:MM" strings that a rule-based
step validates and converts afterwards (invariant 4). Unknown means null, not a guess
(invariant 8).
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.llm.provider import LLMProvider

MAX_TEXT_CHARS = 8000  # a few days of notes; longer pasted text is refused before any LLM call

SYSTEM_PROMPT = """\
You turn a traveler's pasted itinerary (from a notepad, a chat or a spreadsheet) into a form.
Split it into days in the order written. For every place or activity give:
- title: the words used in the text, not translated or "fixed".
- start / end: 24-hour "HH:MM" exactly as written ("오후 3시" -> "15:00"). If the text gives
  only a start time, leave end null. If it gives no time, leave both null. Never invent a time.
- category: meal, sightseeing, shopping, cafe, transport or other. Use other when unclear.
- reserved: true only if the text says it is booked or reserved ("예약", "reservation").
- note: anything else written on that line (price, address, reminder), or null.

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
