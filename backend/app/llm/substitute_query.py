"""Step ⑦ (part): what kind of place could stand in for a closed one (LLM call #4).

The LLM only names a kind of place ("이자카야 저녁" -> "이자카야"). It never names a real
place: Google Places finds those, and code checks their opening hours. If the model fails or
gives something unusable, the activity title itself is the search text (invariant 4).
"""

from pydantic import BaseModel, Field

from app.llm.provider import LLMOutputError, LLMProvider

MAX_QUERY_CHARS = 30

SYSTEM_PROMPT = """\
A traveler's plan item is closed today. Give a short map-search phrase for OTHER places of the
same kind that could replace it, in the language of the title.
- Name the kind of place, not this specific place or brand: "이치란 라멘 점심" -> "라멘",
  "블루보틀 커피" -> "카페", "이자카야 저녁" -> "이자카야", "teamLab Planets" -> "디지털 아트 전시".
- Drop meal times and filler words ("점심", "저녁", "예약", "가기").
- If you cannot tell what kind of place it is, answer null.
- If indoor is yes, the item is outdoors and it is raining or the traveler wants to stay inside:
  name an INDOOR kind of place for a similar purpose ("메이지 신궁" -> "박물관",
  "공원 산책" -> "실내 정원", "야시장" -> "푸드홀").
"""


class SubstituteQuery(BaseModel):
    query: str | None = Field(description="short search phrase, or null")


def substitute_query(provider: LLMProvider, title: str, category: str, indoor: bool = False) -> str:
    """Search text for places like `title`. Falls back to the title; never raises for LLM trouble.
    `indoor`: an inside place is wanted (the fallback then asks Google for "실내 <title>")."""
    fallback = f"실내 {title}" if indoor else title
    user = f"title: {title}\ncategory: {category}" + ("\nindoor: yes" if indoor else "")
    try:
        answer = provider.complete_json(system=SYSTEM_PROMPT, user=user, schema=SubstituteQuery)
    except LLMOutputError:
        return fallback
    query = (answer.query or "").strip()
    if not query or len(query) > MAX_QUERY_CHARS:
        return fallback
    return query
