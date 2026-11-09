from typing import Literal

from pydantic import Field, model_validator

from app.schemas.enums import Op, ReasonType
from app.schemas.events import DelayEvent, DisruptionEvent
from app.schemas.models import (
    HOTEL_ID,
    MINUTES_PER_DAY,
    Activity,
    Day,
    Preference,
    Substitute,
    TravelTime,
    _Frozen,
)


class Slot(_Frozen):
    start: int = Field(ge=0, le=MINUTES_PER_DAY)
    end: int = Field(ge=0, le=MINUTES_PER_DAY)

    @model_validator(mode="after")
    def _check_order(self) -> "Slot":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class ReasonData(_Frozen):
    """The solver's own numbers behind a change. Sentences are filled from these and never
    invented (CLAUDE.md rule 5). Which fields are set depends on the reason type."""

    forced_by: tuple[str, ...] = ()  # binding: validator kinds that rule out the original slot
    value: int | None = None  # value: the activity's tier weight
    minutes_saved: int | None = None  # value: minutes the cut frees for the rest of the day
    value_lost: float | None = None  # value: weight x share of the activity that is lost


class RecoveryChange(_Frozen):
    activity_id: str
    op: Op
    before: Slot | None = None
    after: Slot | None = None
    reason_type: ReasonType | None = None  # None = kept, or no reason could be established
    reason_data: ReasonData | None = None
    substitute_id: str | None = None  # set exactly when op is SUBSTITUTE
    needs_check: bool = False  # unknown to us: tell the user to check on site

    @model_validator(mode="after")
    def _check_slots_match_op(self) -> "RecoveryChange":
        if self.op == Op.ADD:
            ok = self.before is None and self.after is not None
        elif self.op == Op.DROP:
            ok = self.before is not None and self.after is None
        elif self.op == Op.KEEP:
            ok = self.before is not None and self.before == self.after
        else:
            ok = self.before is not None and self.after is not None
        if not ok:
            raise ValueError(f"before/after do not match op={self.op}")
        if (self.op == Op.SUBSTITUTE) != (self.substitute_id is not None):
            raise ValueError("substitute_id is required for, and only for, op=substitute")
        return self


class Blocker(_Frozen):
    """A hard constraint that on its own rules out every plan (why recover() came back empty).

    Only certain causes are reported; an empty list means "no single cause found".
    """

    kind: Literal["reserved_in_past", "reserved_in_rain", "extension_blocked"]
    activity_id: str
    blocking_time: int | None = None  # the time that cannot move (a reservation)
    max_extra_minutes: int | None = None  # extension_blocked: the most that would still fit


class RcBreakdown(_Frozen):
    d_drop: float = 0.0
    d_shrink: float = 0.0
    d_sub: float = 0.0
    d_order: float = 0.0
    d_time: float = 0.0
    d_move: float = 0.0
    d_intent: float = 0.0
    d_changed: float = 0.0


class RecoveryResult(_Frozen):
    strategy: str
    changes: tuple[RecoveryChange, ...]
    rc_total: float
    rc_breakdown: RcBreakdown
    preservation_rate: float = Field(ge=0.0, le=1.0)
    violations: int = Field(ge=0)
    solver_ms: int = Field(ge=0)


class RecoveryResponse(_Frozen):
    """What the API returns: the candidates, or, when none exists, the blockers explaining why."""

    candidates: tuple[RecoveryResult, ...]
    blockers: tuple[Blocker, ...] = ()


class RecoveryInput(_Frozen):
    day: Day
    activities: tuple[Activity, ...]
    preferences: tuple[Preference, ...]
    travel: tuple[TravelTime, ...]
    event: DisruptionEvent
    substitutes: tuple[Substitute, ...] = ()

    @property
    def now(self) -> int:
        # A delayed user can move again at start_time; otherwise "now" is occurred_at.
        ev = self.event
        return ev.start_time if isinstance(ev, DelayEvent) else ev.occurred_at

    @model_validator(mode="after")
    def _check_references(self) -> "RecoveryInput":
        ids = [a.id for a in self.activities]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate activity id")
        pref_ids = [p.activity_id for p in self.preferences]
        if len(set(pref_ids)) != len(pref_ids):
            raise ValueError("duplicate preference for an activity")
        if set(pref_ids) != set(ids):
            raise ValueError("every activity needs exactly one preference")
        target = getattr(self.event, "activity_id", None)
        if target is not None and self.event.type != "MUST_VISIT" and target not in ids:
            raise ValueError(f"event references unknown activity: {target}")
        self._check_substitutes(ids)
        self._check_travel_table(ids, target)
        return self

    def _check_substitutes(self, ids: list[str]) -> None:
        sub_ids = [s.id for s in self.substitutes]
        if len(set(sub_ids)) != len(sub_ids) or set(sub_ids) & {HOTEL_ID, *ids}:
            raise ValueError("substitute ids must be unique and differ from every other node")
        unknown = {s.replaces for s in self.substitutes} - set(ids)
        if unknown:
            raise ValueError(f"substitute replaces unknown activity: {sorted(unknown)}")

    def _check_travel_table(self, ids: list[str], target: str | None) -> None:
        nodes = {HOTEL_ID, *ids, *(s.id for s in self.substitutes)}
        if self.event.type == "MUST_VISIT" and target is not None:
            nodes.add(target)
        if self.event.location_id not in nodes:
            raise ValueError(f"unknown current location: {self.event.location_id}")
        seen: set[frozenset[str]] = set()
        for t in self.travel:
            pair = frozenset((t.a, t.b))
            if len(pair) != 2 or not pair <= nodes:
                raise ValueError(f"bad travel pair: {t.a}-{t.b}")
            if pair in seen:
                raise ValueError(f"duplicate travel pair: {t.a}-{t.b}")
            seen.add(pair)
        expected = len(nodes) * (len(nodes) - 1) // 2
        if len(seen) != expected:
            raise ValueError(f"travel table incomplete: {len(seen)} of {expected} pairs")
