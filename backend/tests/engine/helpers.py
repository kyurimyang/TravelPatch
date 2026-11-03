import json
from pathlib import Path

from app.schemas.enums import Op
from app.schemas.recovery import RecoveryChange, RecoveryInput, Slot

# The recovery table of scenario A from the planning doc (minutes since midnight).
# None = dropped. Boundary case on purpose: harajuku starts exactly at 730 + 5 travel.
SOLUTION_A: dict[str, tuple[int, int] | None] = {
    "meiji": (680, 730),
    "harajuku": (735, 780),
    "omotesando": None,
    "ramen": (795, 855),
    "shibuya_shop": (875, 965),
    "cafe": (970, 1005),
    "sky": (1020, 1080),
    "izakaya": (1170, 1260),
}


# Scenario E as drawn in the planning doc: lunch onwards unchanged, omotesando shrunk to 30.
SOLUTION_E: dict[str, tuple[int, int] | None] = {
    "harajuku": (630, 720),
    "omotesando": (730, 760),
    "ramen": (770, 830),
    "shibuya_shop": (850, 940),
    "cafe": (950, 995),
    "sky": (1020, 1080),
    "izakaya": (1170, 1260),
}


def load_scenario(name: str) -> RecoveryInput:
    path = Path(__file__).parents[1] / "scenarios" / name
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop("expected")
    return RecoveryInput.model_validate(raw)


def load_scenario_a() -> RecoveryInput:
    return load_scenario("scenario_a.json")


def original_plan(inp: RecoveryInput) -> dict[str, tuple[int, int] | None]:
    return {a.id: (a.planned_start, a.planned_end) for a in inp.activities}


def plan(
    inp: RecoveryInput,
    base: dict[str, tuple[int, int] | None] | None = None,
    **override: tuple[int, int] | None,
) -> tuple[RecoveryChange, ...]:
    """Changes for every activity: `base` (default SOLUTION_A) with some overridden."""
    target = {**(SOLUTION_A if base is None else base), **override}
    changes = []
    for a in inp.activities:
        before = Slot(start=a.planned_start, end=a.planned_end)
        slot = target[a.id]
        if slot is None:
            changes.append(RecoveryChange(activity_id=a.id, op=Op.DROP, before=before))
            continue
        after = Slot(start=slot[0], end=slot[1])
        if after == before:
            op = Op.KEEP
        elif after.end - after.start < before.end - before.start:
            op = Op.SHRINK
        elif after.end - after.start > before.end - before.start:
            op = Op.EXTEND
        else:
            op = Op.MOVE
        changes.append(RecoveryChange(activity_id=a.id, op=op, before=before, after=after))
    return tuple(changes)


def load_scenario_c() -> RecoveryInput:
    raw = json.loads((Path(__file__).parents[1] / "scenarios" / "scenario_c.json").read_text(encoding="utf-8"))
    raw.pop("expected")
    return RecoveryInput.model_validate(raw)


def plan_c(
    inp: RecoveryInput, izakaya: tuple[int, int] | None, sub: str | None = None
) -> tuple[RecoveryChange, ...]:
    """Everything kept as planned; only the izakaya (closed) is replaced by `sub` at `izakaya`."""
    out = []
    for a in inp.activities:
        before = Slot(start=a.planned_start, end=a.planned_end)
        if a.id != "izakaya":
            out.append(RecoveryChange(activity_id=a.id, op=Op.KEEP, before=before, after=before))
        elif izakaya is None:
            out.append(RecoveryChange(activity_id=a.id, op=Op.DROP, before=before))
        else:
            after = Slot(start=izakaya[0], end=izakaya[1])
            if sub is None:
                out.append(RecoveryChange(activity_id=a.id, op=Op.KEEP, before=before, after=before))
            else:
                out.append(
                    RecoveryChange(
                        activity_id=a.id, op=Op.SUBSTITUTE, before=before, after=after, substitute_id=sub
                    )
                )
    return tuple(out)
