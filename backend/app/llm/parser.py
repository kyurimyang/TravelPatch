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
Split it into days in the order written, and each day into items.

An item is one block: a line with a time, together with the lines under it up to the next line
with a time ("주소: ...", "위치: ...", "활동: ...", a list of names). A line without a time and
without lines under it is an item of its own.

For every item give:
- title: what the block is, exactly as written, not translated or "fixed": the words on the
  time line after the time, or else the first line under it. Never the time itself.
- start / end: 24-hour "HH:MM" exactly as written ("오후 3시" -> "15:00"). If the text gives
  only a start time, leave end null. If it gives no time, leave both null. Never invent a time.
- role: what the block is in the day, judged by what it ends with:
  activity (a place to spend time at: sight, meal, cafe, shop, show),
  transport (moving between places, a route; "이동", "복귀" to somewhere),
  lodging (at the traveler's own hotel: check-in, check-out, bags, back at the hotel to rest),
  airport (at an airport: arrival, immigration, check-in for a flight, security, boarding).
  "호텔까지 이동 및 짐 보관" is lodging, "산책 및 식당으로 이동" is transport,
  "호텔 조식" is an activity.
- category: meal, sightseeing, shopping, cafe, transport or other. Use other when unclear.
- patch: what kind of place it is, judged from the name in any language, or null when the line
  is none of these or you are not sure: worship (temple, shrine, church, mosque), museum
  (museum, gallery, aquarium), viewpoint (observation deck, tower, night view), bar (bar, pub,
  izakaya), market (market, night market), nature (park, garden, mountain, lake), spa (hot
  spring, spa, sauna), beach, lodging (hotel, check-in), theme_park (amusement park, theme park,
  zoo), venue (concert hall, theater, stadium, show), mall (shopping mall, department store).
- reserved: true only if the text says it is booked or reserved ("예약", "reservation").
- place_query: only the name of the place to look up on a map, copied from the block as
  written, without activity words ("오모테산도 산책" -> "오모테산도", "이치란 라멘 점심" ->
  "이치란 라멘"). For a transport block, the place it goes to. For an airport or lodging
  block, the airport or hotel ("나리타 국제공항 도착 및 입국 수속" -> "나리타 국제공항").
  null when the block names no
  particular place ("점심 - 스시", "쇼핑"). Never add a name that is not written.
- address: the street address written in the block ("주소: ..."), copied exactly, or null.
- within: the larger place this block happens inside, when the text shows it: copy that place's
  name exactly as it is written somewhere in the same day (a "위치:" line, the day's subtitle,
  or an earlier block). Example: on a day subtitled "도쿄 디즈니랜드 종일 관광", lunch at
  "Queen of Hearts" is within "도쿄 디즈니랜드". null when the block is a place of its own or
  you are not sure.
- spot: the exact spot inside that larger place as written ("장소: ...", "위치: ..."), or null.
- note: the other lines of the block (menu, activities, route, reminders) as written, or null.
  Do not repeat what is already in address or spot.

Rules:
- Do not add, merge, reorder or drop items.
- day_label is the day's heading copied exactly as written ("DAY 2. 1월 25일 (월)", "2일차",
  "10/8"), or null. Never number the days yourself.
- start and end come from the block's time line: "13:00~16:00" is start "13:00", end "16:00".
- theme: a line right under the heading that sums up the day ("나리타 도착 → 신주쿠 관광"),
  copied as written, or null. It is not an item.
- If a day has no heading, still make a day for it, with day_label null.
"""

# What a block is in the day. Only `activity` becomes an item the engine plans; the rule step
# turns transport blocks into legs and lodging/airport blocks into the hotel and the flights.
Role = Literal["activity", "transport", "lodging", "airport"]


class ParsedItem(BaseModel):
    title: str
    start: str | None = Field(description="HH:MM as written, or null")
    end: str | None = Field(description="HH:MM as written, or null")
    category: Literal["meal", "sightseeing", "shopping", "cafe", "transport", "other"]
    role: Role
    reserved: bool
    note: str | None
    place_query: str | None = Field(description="place name as written in the block, or null")
    address: str | None = Field(description="street address as written, or null")
    within: str | None = Field(description="larger place's name as written in the day, or null")
    spot: str | None = Field(description="spot inside the larger place as written, or null")
    patch: PatchKind | None = Field(description="kind of place, or null")


class ParsedDay(BaseModel):
    day_label: str | None
    theme: str | None = Field(description="the day's subtitle line as written, or null")
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
