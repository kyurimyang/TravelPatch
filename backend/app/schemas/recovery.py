from pydantic import Field, model_validator

from app.schemas.enums import Op, ReasonType
from app.schemas.events import DisruptionEvent
from app.schemas.models import (
    HOTEL_ID,
    MINUTES_PER_DAY,
    Activity,
    Day,
    Preference,
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


class RecoveryChange(_Frozen):
    activity_id: str
    op: Op
    before: Slot | None = None
    after: Slot | None = None
    reason_type: ReasonType | None = None

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
        return self


class RcBreakdown(_Frozen):
    d_drop: float = 0.0
    d_shrink: float = 0.0
    d_sub: float = 0.0
    d_order: float = 0.0
    d_time: float = 0.0
    d_move: float = 0.0
    d_intent: float = 0.0


class RecoveryResult(_Frozen):
    strategy: str
    changes: tuple[RecoveryChange, ...]
    rc_total: float
    rc_breakdown: RcBreakdown
    preservation_rate: float = Field(ge=0.0, le=1.0)
    violations: int = Field(ge=0)
    solver_ms: int = Field(ge=0)


class RecoveryInput(_Frozen):
    day: Day
    activities: tuple[Activity, ...]
    preferences: tuple[Preference, ...]
    travel: tuple[TravelTime, ...]
    event: DisruptionEvent

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
        self._check_travel_table(ids, target)
        return self

    def _check_travel_table(self, ids: list[str], target: str | None) -> None:
        nodes = {HOTEL_ID, *ids}
        if self.event.type == "MUST_VISIT" and target is not None:
            nodes.add(target)
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
