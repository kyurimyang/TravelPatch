"""Comparison experiment: solve every scenario with each method, write CSV + markdown table.

    python -m eval.run --scenarios backend/tests/scenarios --out eval/results

Timing lives here, not in the engine (the engine never reads the clock).
"""

import argparse
import csv
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

from app.engine.baselines import greedy, right_shift
from app.engine.conflict_detector import find_blockers
from app.engine.cost import compute_cost
from app.engine.presets import DEFAULT_WEIGHTS
from app.engine.recover import recover
from app.schemas.enums import Op
from app.schemas.recovery import RecoveryInput, RecoveryResult


def _engine(inp: RecoveryInput) -> RecoveryResult | None:
    # The engine returns several candidates; the one with the best preservation represents it.
    results = recover(inp)
    return max(results, key=lambda r: r.preservation_rate) if results else None


METHODS: dict[str, Callable[[RecoveryInput], RecoveryResult | None]] = {
    "right_shift": right_shift,
    "greedy": greedy,
    "engine": _engine,
}
FIELDS = ["scenario", "method", "violations", "preservation", "rc_total", "dropped", "solver_ms", "no_solution_reason"]


def _load(path: Path) -> RecoveryInput:
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop("expected", None)
    return RecoveryInput.model_validate(raw)


def run(scenario_dir: Path) -> list[dict]:
    rows = []
    for path in sorted(scenario_dir.glob("*.json")):
        inp = _load(path)
        for name, method in METHODS.items():
            t0 = time.perf_counter()
            result = method(inp)
            ms = round((time.perf_counter() - t0) * 1000, 1)
            if result is None:  # no valid plan exists: not the same as "0 violations"
                why = "; ".join(f"{b.kind}:{b.activity_id}" for b in find_blockers(inp)) or "unknown"
                rows.append({"scenario": path.stem, "method": name, "violations": "", "preservation": "",
                             "rc_total": "", "dropped": "", "solver_ms": ms, "no_solution_reason": why})
                continue
            rows.append({
                "scenario": path.stem, "method": name, "violations": result.violations,
                "preservation": round(result.preservation_rate, 4), "rc_total": round(compute_cost(inp, result.changes, DEFAULT_WEIGHTS).rc_total, 3),  # same weights for all
                "dropped": sum(c.op == Op.DROP for c in result.changes), "solver_ms": ms,
            })
    return rows


def _mean(rows: list[dict], key: str) -> float:
    return sum(r[key] for r in rows) / len(rows)


def _event(r: dict) -> str:
    return r["scenario"].split("_")[-1]  # i03_delay -> delay, scenario_a -> a


def _valid(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["violations"] == 0]


def _stats(rows: list[dict]) -> tuple[str, str, str]:
    """Preservation / RC / ms over the rows (only call with violation-free rows)."""
    if not rows:
        return "-", "-", "-"
    return f"{_mean(rows, 'preservation'):.1%}", f"{_mean(rows, 'rc_total'):.3f}", f"{_mean(rows, 'solver_ms'):.1f}"


def summarize(rows: list[dict]) -> list[str]:
    """Violating plans must not flatter a method: preservation and RC use violation-free rows."""
    out = [
        "### All scenarios",
        "",
        "| method | scenarios | no solution | violation rate | violation-free | preservation (violation-free) | RC (violation-free) | ms (all) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name in METHODS:
        mine = [r for r in rows if r["method"] == name]
        solved = [r for r in mine if r["violations"] != ""]
        good = _valid(solved)
        pres, rc, _ = _stats(good)
        rate = f"{sum(r['violations'] > 0 for r in solved) / len(solved):.0%}" if solved else "-"
        ms = f"{_mean(solved, 'solver_ms'):.1f}" if solved else "-"
        out.append(f"| {name} | {len(mine)} | {len(mine) - len(solved)} | {rate} | {len(good)} | {pres} | {rc} | {ms} |")

    events = sorted({_event(r) for r in rows})
    out += ["", "### Violation rate by event (no solution counted separately)", "",
            "| method | " + " | ".join(events) + " |", "|---|" + "---|" * len(events)]
    for name in METHODS:
        cells = []
        for ev in events:
            mine = [r for r in rows if r["method"] == name and _event(r) == ev]
            solved = [r for r in mine if r["violations"] != ""]
            bad = sum(r["violations"] > 0 for r in solved)
            none = len(mine) - len(solved)
            cells.append(f"{bad}/{len(solved)}" + (f" (+{none} none)" if none else ""))
        out.append(f"| {name} | " + " | ".join(cells) + " |")

    # Head to head: only scenarios where EVERY method produced a violation-free plan.
    ok = {name: {r["scenario"]: r for r in _valid(rows) if r["method"] == name} for name in METHODS}
    common = sorted(set.intersection(*(set(d) for d in ok.values())))
    out += ["", f"### Same {len(common)} scenarios where all methods are violation-free", "",
            "| method | preservation | RC | dropped (mean) |", "|---|---|---|---|"]
    for name in METHODS:
        picked = [ok[name][sc] for sc in common]
        if picked:
            out.append(f"| {name} | {_mean(picked, 'preservation'):.1%} | {_mean(picked, 'rc_total'):.3f} | {_mean(picked, 'dropped'):.2f} |")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=Path, default=Path("backend/tests/scenarios"))
    ap.add_argument("--out", type=Path, default=Path("eval/results"))
    args = ap.parse_args()
    rows = run(args.scenarios)
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "results.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)
    table = "\n".join(summarize(rows)) + "\n"
    (args.out / "summary.md").write_text(table, encoding="utf-8")
    print(table)


if __name__ == "__main__":
    main()
