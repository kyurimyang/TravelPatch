"""Step ④: free text ("늦잠 잤어") -> a loose `InterpretedDisruption` (LLM call #2 of 3).

The LLM only fills in what the user literally said. It never computes absolute times or picks
activity ids: a rule-based step turns this into a `DisruptionEvent` afterwards (invariant 4).
The result is shown to the user as chips and can be edited before the engine runs.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.llm.provider import LLMProvider

SYSTEM_PROMPT = """\
You read one short message from a traveler whose day plan broke, and fill in a form.
Pick exactly one type:
- DELAY: the traveler is running late or cannot move for a while (oversleeping, a delay).
- WEATHER: rain or bad weather starting at some time.
- CLOSURE: a place in the plan is closed or unavailable.
- FATIGUE: the traveler or a companion is tired and wants less walking.
- EXTEND: the traveler wants to stay longer at one place of the plan.
- RESERVATION_CHANGE: a reservation moved to another time.
- MUST_VISIT: the traveler insists on visiting a place that is not in the plan.
- UNKNOWN: none of the above fits, or the message is unclear.

Rules:
- Copy only what the message says. If a field is not stated, use null. Never guess a number.
- Convert spoken durations to minutes ("2시간" -> 120, "반나절" is not stated -> null).
- Times are 24-hour "HH:MM" strings exactly as stated ("12시부터" -> "12:00").
- activity_hint is the words the traveler used for a place in the plan ("저녁 식당",
  "하라주쿠"). Do not translate it and do not turn it into an id.
"""


class InterpretedDisruption(BaseModel):
    # OpenAI structured output needs every field present, so optional ones are `| None`
    # with no default; the model must write null explicitly.
    type: Literal[
        "DELAY",
        "WEATHER",
        "CLOSURE",
        "FATIGUE",
        "EXTEND",
        "RESERVATION_CHANGE",
        "MUST_VISIT",
        "UNKNOWN",
    ]
    delay_minutes: int | None = Field(description="DELAY: how long from now, in minutes")
    time_from: str | None = Field(description="WEATHER: start time, HH:MM")
    time_to: str | None = Field(description="WEATHER: end time, HH:MM")
    activity_hint: str | None = Field(description="CLOSURE/EXTEND/RESERVATION_CHANGE/MUST_VISIT")
    extra_minutes: int | None = Field(description="EXTEND: extra minutes at the place")
    new_time: str | None = Field(description="RESERVATION_CHANGE: new time, HH:MM")


def interpret(provider: LLMProvider, text: str) -> InterpretedDisruption:
    """Raises `LLMOutputError` when the provider fails twice; the caller then asks the user."""
    return provider.complete_json(
        system=SYSTEM_PROMPT, user=text.strip(), schema=InterpretedDisruption
    )
