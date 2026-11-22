"""Why did each activity change? Classified after the solve, with the validator as the oracle.

For a changed activity X: put X back where the original plan had it (everything else as the
solver chose) and ask the validator what breaks for X itself.

- A hard constraint other than travel time breaks (past, closure, reservation, hours, weather,
  ...): the change was forced. reason_type = binding, with those kinds in reason_data.
- Only travel time breaks (X would overlap its neighbours): that is true of any activity you
  would put back, so it does not say why X was picked. A shrink or drop is then a choice of
  value (what is lost vs the minutes freed); a move is a ripple from the activities before it
  (binding on travel).
- Nothing breaks and it is not a cut: no reason can be established, so none is claimed
  (CLAUDE.md rule 8).

Does not import the solver: it reads the input and the finished changes only. Pure, no clock.
"""

from app.engine.validator import validate
from app.schemas.enums import Op, ReasonType
from app.schemas.recovery import ReasonData, RecoveryChange, RecoveryInput


def explain_changes(
    inp: RecoveryInput, changes: tuple[RecoveryChange, ...], min_buffer: int, **rules
) -> tuple[RecoveryChange, ...]:
    """The same changes, in the same order, with reason_type and reason_data filled in."""
    weight = {p.activity_id: p.tier.weight for p in inp.preferences}
    # `rules`: the strategy's own hard rules (candidate.strategy_rules), as validate() takes them.
    return tuple(_explain(inp, changes, c, weight, min_buffer, rules) for c in changes)


def _explain(
    inp: RecoveryInput,
    changes: tuple[RecoveryChange, ...],
    change: RecoveryChange,
    weight: dict[str, int],
    min_buffer: int,
    rules: dict,
) -> RecoveryChange:
    if change.op in (Op.KEEP, Op.ADD):
        return change
    own = _own_violations(inp, changes, change, min_buffer, rules)
    forced = tuple(k for k in own if k != "travel")
    if forced:
        data = ReasonData(forced_by=forced)
        return change.model_copy(update={"reason_type": ReasonType.BINDING, "reason_data": data})
    if change.op in (Op.SHRINK, Op.DROP):
        return change.model_copy(
            update={"reason_type": ReasonType.VALUE, "reason_data": _value_data(change, weight)}
        )
    if own:  # only travel time: a ripple from earlier changes
        data = ReasonData(forced_by=own)
        return change.model_copy(update={"reason_type": ReasonType.BINDING, "reason_data": data})
    return change


def _own_violations(
    inp: RecoveryInput,
    changes: tuple[RecoveryChange, ...],
    change: RecoveryChange,
    min_buffer: int,
    rules: dict,
) -> tuple[str, ...]:
    """Kinds of violation that land on this activity once it is put back in its original slot."""
    restored = RecoveryChange(
        activity_id=change.activity_id, op=Op.KEEP, before=change.before, after=change.before
    )
    plan = tuple(restored if c.activity_id == change.activity_id else c for c in changes)
    kinds = {v.kind for v in validate(inp, plan, min_buffer, **rules) if v.activity_id == change.activity_id}
    return tuple(sorted(kinds))


def _value_data(change: RecoveryChange, weight: dict[str, int]) -> ReasonData:
    assert change.before is not None  # a shrink or drop always has an original slot
    value = weight[change.activity_id]
    before_len = change.before.end - change.before.start
    after_len = 0 if change.after is None else change.after.end - change.after.start
    saved = before_len - after_len
    # Same formula as cost.py's D_shrink; a drop (after_len 0) loses the whole value.
    return ReasonData(value=value, minutes_saved=saved, value_lost=value * saved / before_len)
