"""LLM-only recovery (comparison methods (c) and (d)): prompt, answer schema, conversion.

The LLM gets the same facts the engine gets, in plain words, and writes a whole new plan.
Nothing here is a product path: it exists to measure what an LLM does without a solver.
Times go in and out as "HH:MM", like a person would write them.
"""

import re
from typing import Literal

from pydantic import BaseModel

from app.engine.presets import MEAL_WINDOW_MINUTES
from app.engine.validator import Violation
from app.schemas.enums import Category, Op, Tier
from app.schemas.events import (
    ClosureEvent,
    DelayEvent,
    ExtendEvent,
    FatigueEvent,
    WeatherEvent,
)
from app.schemas.models import HOTEL_ID, MINUTES_PER_DAY
from app.schemas.recovery import RecoveryChange, RecoveryInput, Slot

SYSTEM_PROMPT = """\
You repair a traveler's broken one-day plan. Write the new schedule for every activity.
Change as little as possible: leave activities as planned when you can, shorten or move
before dropping, and drop the least important ones last. All times are 24-hour "HH:MM".

Hard rules (a plan that breaks any of them is unusable):
- Nothing may start before the current time. The activity the traveler is in right now has
  already started: its start cannot change and it cannot end before now.
- Travel time between places is given. Each activity must start at least that many minutes
  after the previous one ends (the first one: after now, counting travel from the traveler's
  current place). Activities cannot overlap.
- An activity with a reservation must start exactly at the reserved time.
- Stay inside opening hours (start >= opens, end <= closes) when they are given.
- A meal (marked "meal: start between ...") must start inside that window, a replacement for it
  too; if it cannot, drop it.
- An activity can be shortened but never below its minimum duration.
- Activities marked MUST cannot be dropped.
- The traveler must be back at the hotel, including travel time, by the deadline.

For each activity answer with action "keep" (exactly as planned), "change" (give the new
start and end) or "drop" (start and end null).
"""


class PlanItem(BaseModel):
    activity_id: str
    action: Literal["keep", "change", "drop", "substitute"]
    start: str | None
    end: str | None
    # Only for "substitute". Default so answers recorded before this field existed still load.
    substitute_id: str | None = None


class LLMPlan(BaseModel):
    items: list[PlanItem]


class PlanFormatError(ValueError):
    """The answer cannot be turned into a plan (bad time text, impossible slot)."""


_TIME_RE = re.compile(r"^(?:([01]?\d|2[0-3]):([0-5]\d)|24:00)$")


def hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_hhmm(text: str) -> int:
    match = _TIME_RE.match(text.strip())
    if match is None:
        raise PlanFormatError(f"bad time: {text!r}")
    return MINUTES_PER_DAY if match.group(1) is None else int(match.group(1)) * 60 + int(match.group(2))


def _describe_event(inp: RecoveryInput) -> str:
    ev = inp.event
    title = {a.id: a.title for a in inp.activities}
    match ev:
        case DelayEvent():
            return f"The traveler overslept or was delayed and can only start moving at {hhmm(ev.start_time)}."
        case WeatherEvent():
            end = hhmm(ev.end_time) if ev.end_time is not None else "the end of the day"
            return (
                f"It rains from {hhmm(ev.start_time)} to {end}. Outdoor activities (marked outdoor) "
                "must not overlap that time."
            )
        case ClosureEvent():
            closed = f"{title[ev.activity_id]} ({ev.activity_id}) is closed today and cannot be visited"
            if any(s.replaces == ev.activity_id for s in inp.substitutes):
                return f"{closed}: replace it with one of the replacement places below, or drop it."
            return f"{closed}: drop it."
        case FatigueEvent():
            return (
                f"The group is tired. Activities marked walking, except reserved ones, may last at most "
                f"{ev.walking_ratio:.0%} of their planned length (rounded up to 5 minutes, never below the minimum)."
            )
        case ExtendEvent():
            return (
                f"The traveler wants {ev.extra_minutes} more minutes at {title[ev.activity_id]} "
                f"({ev.activity_id}): it must last its planned length plus {ev.extra_minutes} minutes."
            )
        case _:
            raise PlanFormatError(f"event type not supported in the LLM experiment: {ev.type}")


def build_prompt(inp: RecoveryInput) -> str:
    tier = {p.activity_id: p.tier for p in inp.preferences}
    here = inp.event.location_id
    lines = [
        f"Current time (when moving is possible): {hhmm(inp.now)}",
        f"Traveler is at: {'the hotel' if here == HOTEL_ID else here}",
        f"Back at the hotel by: {hhmm(inp.day.end_deadline)}",
        f"What happened: {_describe_event(inp)}",
        "",
        "Planned activities (id | title | planned | min minutes | importance | notes):",
    ]
    for a in sorted(inp.activities, key=lambda a: (a.planned_start, a.id)):
        notes = []
        if a.reservation_time is not None:
            notes.append(f"reserved at {hhmm(a.reservation_time)}")
        if a.open_at is not None:
            notes.append(f"opens {hhmm(a.open_at)}")
        if a.close_at is not None:
            notes.append(f"closes {hhmm(a.close_at)}")
        if a.category == Category.MEAL:
            # The engine's meal window (A3, 2026-11-19), told as numbers like opening hours.
            lo = max(0, a.planned_start - MEAL_WINDOW_MINUTES)
            hi = min(MINUTES_PER_DAY, a.planned_start + MEAL_WINDOW_MINUTES)
            notes.append(f"meal: start between {hhmm(lo)} and {hhmm(hi)}")
        if a.outdoor:
            notes.append("outdoor")
        if a.walking:
            notes.append("walking")
        importance = "MUST" if tier[a.id] == Tier.MUST else tier[a.id].value
        lines.append(
            f"{a.id} | {a.title} | {hhmm(a.planned_start)}-{hhmm(a.planned_end)} | "
            f"{a.min_duration} | {importance} | {', '.join(notes) or '-'}"
        )
    if inp.substitutes:
        lines += [
            "",
            (
                'Replacement places (use action "substitute" with its id and give start and end; '
                "it keeps the importance of the activity it replaces; it has its own hours and "
                "minimum length and no reservation) "
                "(id | replaces | title | usual minutes | min minutes | hours):"
            ),
        ]
        for sub in sorted(inp.substitutes, key=lambda s: s.id):
            hours = f"{hhmm(sub.open_at or 0)}-{hhmm(sub.close_at or MINUTES_PER_DAY)}"
            lines.append(
                f"{sub.id} | {sub.replaces} | {sub.title} | {sub.duration} | {sub.min_duration} | {hours}"
            )
    lines += ["", "Travel minutes between places (either direction):"]
    lines += [f"{t.a} <-> {t.b}: {t.minutes}" for t in sorted(inp.travel, key=lambda t: (t.a, t.b))]
    return "\n".join(lines)


def repair_prompt(inp: RecoveryInput, previous: LLMPlan, problems: list[Violation]) -> str:
    """Same facts, plus the previous answer and what a checker found wrong with it."""
    listed = "\n".join(f"- {v.kind}: {v.detail}" for v in problems)
    return (
        f"{build_prompt(inp)}\n\nYour previous plan:\n{previous.model_dump_json()}\n\n"
        f"A checker found these problems:\n{listed}\n\nWrite a corrected plan."
    )


def plan_to_changes(inp: RecoveryInput, plan: LLMPlan) -> tuple[RecoveryChange, ...]:
    """One change per original activity. An activity the answer leaves out is unchanged."""
    said = {item.activity_id: item for item in plan.items}
    changes = []
    for a in sorted(inp.activities, key=lambda a: (a.planned_start, a.id)):
        before = Slot(start=a.planned_start, end=a.planned_end)
        item = said.get(a.id)
        if item is None or item.action == "keep":
            changes.append(RecoveryChange(activity_id=a.id, op=Op.KEEP, before=before, after=before))
        elif item.action == "drop":
            changes.append(RecoveryChange(activity_id=a.id, op=Op.DROP, before=before))
        else:
            if item.start is None or item.end is None:
                raise PlanFormatError(f"{a.id}: {item.action} needs start and end")
            if item.action == "substitute" and not item.substitute_id:
                raise PlanFormatError(f"{a.id}: substitute needs substitute_id")
            try:
                after = Slot(start=parse_hhmm(item.start), end=parse_hhmm(item.end))
            except ValueError as exc:  # Slot rejects end <= start
                raise PlanFormatError(f"{a.id}: {exc}") from exc
            length_after, length_before = after.end - after.start, before.end - before.start
            if item.action == "substitute":
                changes.append(
                    RecoveryChange(
                        activity_id=a.id,
                        op=Op.SUBSTITUTE,
                        before=before,
                        after=after,
                        substitute_id=item.substitute_id,
                    )
                )
                continue
            if after == before:
                op = Op.KEEP
            elif length_after > length_before:
                op = Op.EXTEND
            elif length_after < length_before:
                op = Op.SHRINK
            else:
                op = Op.MOVE
            changes.append(RecoveryChange(activity_id=a.id, op=op, before=before, after=after))
    return tuple(changes)
