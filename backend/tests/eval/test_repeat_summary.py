import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from eval.repeat_summary import method_stats, run_files, summarize


def _row(method: str, violations: int, preservation: float, none: str = "") -> dict:
    return {
        "method": method,
        "violations": str(violations),
        "preservation": str(preservation),
        "no_solution_reason": none,
    }


def test_stats_count_violations_among_solved_only() -> None:
    rows = [
        _row("llm_only", 0, 0.9),
        _row("llm_only", 2, 0.5),
        _row("llm_only", 0, 0.0, none="parse"),
    ]
    s = method_stats(rows, "llm_only")
    assert s == {"violation_rate": 0.5, "clean": 1, "no_solution": 1, "preservation": 0.9}


def test_summary_shows_mean_and_range_over_runs() -> None:
    run1 = [_row("llm_only", 1, 0.8), _row("llm_only", 0, 0.9)]
    run2 = [_row("llm_only", 1, 0.8), _row("llm_only", 1, 0.9)]
    line = next(l for l in summarize([run1, run2]) if l.startswith("| llm_only"))
    assert "75.0% (50.0%-100.0%)" in line  # violation rate 50% and 100%


def test_run_files_put_run_one_first_then_by_number(tmp_path) -> None:
    for d in ("run10", "run2"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "results.csv").write_text("x", encoding="utf-8")
    (tmp_path / "results.csv").write_text("x", encoding="utf-8")
    assert [p.parent.name for p in run_files(tmp_path)] == [tmp_path.name, "run2", "run10"]
