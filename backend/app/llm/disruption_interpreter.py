"""Step ④: free text -> a loose `InterpretedMessage` (LLM call #2 of 3).

One sentence can say several things ("비가 오고, 예약이 1시간 당겨졌고, 점심은 대기 40분"), so the
LLM lists every event it hears, plus the traveller's wishes ("실내에 있고 싶어요"). It only fills
in what the user literally said: no clock arithmetic, no activity ids. A rule-based step
(services/event_builder.py) turns each item into a `DisruptionEvent` afterwards, filling the
usual gaps by rule ("no time said" -> now) or asking (invariant 4). The result is shown as
chips the user can fix or remove before the engine runs.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.llm.provider import LLMProvider

SYSTEM_PROMPT = """\
You read one short message from a traveler whose day plan broke, and fill in a form.
List EVERY separate thing that happened, in the order said, one item each:
- DELAY: the traveler is running late or cannot move for a while (oversleeping, a late train).
- WEATHER: rain or bad weather (now, from some time, or all day).
- CLOSURE: a place in the plan is closed or unavailable.
- FATIGUE: the traveler or a companion is tired.
- EXTEND: the traveler wants to stay longer at one place of the plan.
- WAIT: a queue or waiting time at one place of the plan ("대기 40분", "줄이 길어서 30분").
- RESERVATION_CHANGE: a reservation moved to another time, or earlier/later by some amount.
- MUST_VISIT: the traveler insists on visiting a place that is not in the plan.
- UNKNOWN: something happened but none of the above fits.
Also list wishes about the rest of the day, if said:
- indoor: wants to stay inside ("실내에서", "비 안 맞는 곳").
- less_walking: wants to walk less.
- rest: wants to rest or take it easy.
A wish alone is fine: then events may be empty.

Rules:
- Copy only what the message says. If a field is not stated, use null. Never guess a number.
- Never compute clock times. "1시간 앞당겨졌어" -> shift_minutes -60, new_time null.
  "30분 늦춰졌어" -> shift_minutes 30. Only an explicit clock time goes in new_time.
- Convert spoken durations to minutes ("2시간" -> 120, "반나절" is not a number -> null).
- Times are 24-hour "HH:MM" strings exactly as stated ("12시부터" -> "12:00").
- whole_day is true only when the message says all day ("하루종일", "종일", "오늘 내내").
- activity_hint is the words the traveler used for a place in the plan ("점심 식당",
  "런던 아이"). Do not translate it and do not turn it into an id.
"""

EventKind = Literal[
    "DELAY",
    "WEATHER",
    "CLOSURE",
    "FATIGUE",
    "EXTEND",
    "WAIT",
    "RESERVATION_CHANGE",
    "MUST_VISIT",
    "UNKNOWN",
]
WishKind = Literal["indoor", "less_walking", "rest"]


class InterpretedDisruption(BaseModel):
    """One event as heard. OpenAI structured output needs every field present, so optional ones
    are `| None` with no default; the model must write null explicitly."""

    type: EventKind
    delay_minutes: int | None = Field(description="DELAY: how long from now, in minutes")
    time_from: str | None = Field(description="WEATHER: start time, HH:MM, only if stated")
    time_to: str | None = Field(description="WEATHER: end time, HH:MM, only if stated")
    whole_day: bool | None = Field(description="WEATHER: true only if said to last all day")
    activity_hint: str | None = Field(
        description="CLOSURE/EXTEND/WAIT/RESERVATION_CHANGE/MUST_VISIT: the place, as said"
    )
    extra_minutes: int | None = Field(description="EXTEND: extra minutes at the place")
    wait_minutes: int | None = Field(description="WAIT: minutes of queue or waiting")
    new_time: str | None = Field(description="RESERVATION_CHANGE: new clock time, HH:MM")
    shift_minutes: int | None = Field(
        description="RESERVATION_CHANGE: minutes moved, negative = earlier, positive = later"
    )


class InterpretedMessage(BaseModel):
    events: list[InterpretedDisruption]
    wishes: list[WishKind]


def interpret(provider: LLMProvider, text: str) -> InterpretedMessage:
    """Raises `LLMOutputError` when the provider fails twice; the caller then asks the user."""
    return provider.complete_json(
        system=SYSTEM_PROMPT, user=text.strip(), schema=InterpretedMessage
    )
