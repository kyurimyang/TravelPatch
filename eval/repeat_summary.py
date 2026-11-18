"""Repeated LLM runs side by side: mean and range over runs (decision 2026-11-18).

    python -m eval.repeat_summary --out eval/results

Reads eval/results/results.csv (run 1) and eval/results/run2/, run3/, ... and writes
repeat_summary.md. The engine and the baselines are deterministic, so only the LLM methods vary.
"""

import argparse
import csv
from pathlib import Path
from statistics import mean

LLM_METHODS = ("llm_only", "llm_validated")


def run_files(out: Path) -> list[Path]:
    files = [out / "results.csv"]
    files += sorted(out.glob("run*/results.csv"), key=lambda p: int(p.parent.name[3:]))
    return [f for f in files if f.exists()]


def method_stats(rows: list[dict], method: str) -> dict[str, float]:
    mine = [r for r in rows if r["method"] == method]
    solved = [r for r in mine if not r["no_solution_reason"]]
    clean = [r for r in solved if int(r["violations"]) == 0]
    return {
        "violation_rate": (len(solved) - len(clean)) / len(solved) if solved else float("nan"),
        "clean": len(clean),
        "no_solution": len(mine) - len(solved),
        "preservation": mean(float(r["preservation"]) for r in clean) if clean else float("nan"),
    }


def summarize(per_run: list[list[dict]]) -> list[str]:
    lines = [
        f"### LLM methods over {len(per_run)} runs (mean, min-max)",
        "",
        "| method | violation rate | violation-free | no solution | preservation (violation-free) |",
        "|---|---|---|---|---|",
    ]
    for method in LLM_METHODS:
        stats = [method_stats(rows, method) for rows in per_run]

        def cell(key: str, pct: bool) -> str:
            xs = [s[key] for s in stats if s[key] == s[key]]  # drop NaN
            if not xs:
                return "-"
            f = (lambda x: f"{x * 100:.1f}%") if pct else (lambda x: f"{x:.1f}".removesuffix(".0"))
            return f"{f(mean(xs))} ({f(min(xs))}-{f(max(xs))})"

        lines.append(
            f"| {method} | {cell('violation_rate', True)} | {cell('clean', False)} | "
            f"{cell('no_solution', False)} | {cell('preservation', True)} |"
        )
    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("eval/results"))
    args = ap.parse_args()
    files = run_files(args.out)
    per_run = [list(csv.DictReader(f.open(encoding="utf-8"))) for f in files]
    table = "\n".join(summarize(per_run)) + "\n"
    (args.out / "repeat_summary.md").write_text(table, encoding="utf-8")
    print(table)


if __name__ == "__main__":
    main()
