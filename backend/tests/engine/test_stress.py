"""Property tests on seeded random itineraries.

The validator is the oracle: whatever the DP returns must pass it. The DP's own cost must
equal the independently written cost.py. The pruned start candidates must lose nothing
against exploring every 5-minute start.
"""

from itertools import pairwise

import pytest

from app.engine.cost import compute_cost
from app.engine.optimizer_dp import solve_fixed_order
from app.engine.presets import STRATEGIES
from app.engine.recover import recover
from app.engine.validator import validate
from tests.engine.generators import random_instance

# 60 seeds run by default; the rest only with `pytest -m slow`.
SEED_SETS = [range(60), pytest.param(range(60, 300), marks=pytest.mark.slow)]
SMALL_SEED_SETS = [range(12), pytest.param(range(12, 40), marks=pytest.mark.slow)]


def _order(inp) -> tuple[str, ...]:
    return tuple(a.id for a in sorted(inp.activities, key=lambda a: (a.planned_start, a.id)))


def test_instances_are_reproducible() -> None:
    assert random_instance(7) == random_instance(7)
    assert random_instance(7) != random_instance(8)


@pytest.mark.parametrize("seeds", SEED_SETS)
def test_dp_output_always_passes_the_validator(seeds: range) -> None:
    solved = bad = 0
    failures = []
    for seed in seeds:
        inp = random_instance(seed)
        for s in STRATEGIES:
            sol = solve_fixed_order(inp, _order(inp), s.weights, s.min_buffer)
            if sol is None:
                continue
            solved += 1
            violations = validate(inp, sol.changes, s.min_buffer)
            if violations:
                bad += 1
                failures.append((seed, s.name, [(v.kind, v.activity_id) for v in violations]))
    assert solved > 20, "generator is too hard: almost nothing is solvable"
    assert not failures, failures[:5]


@pytest.mark.parametrize("seeds", SEED_SETS)
def test_recover_is_deterministic_and_never_crashes(seeds: range) -> None:
    for seed in seeds:
        inp = random_instance(seed)
        first = recover(inp)
        assert first == recover(inp), seed
        for result in first:
            assert result.violations == 0


@pytest.mark.parametrize("seeds", SEED_SETS)
def test_dp_cost_matches_the_independent_cost_function(seeds: range) -> None:
    mismatches = []
    for seed in seeds:
        inp = random_instance(seed)
        minutes = {frozenset((t.a, t.b)): t.minutes for t in inp.travel}
        order = _order(inp)
        original_route = sum(minutes[frozenset(p)] for p in pairwise(order))
        for s in STRATEGIES:
            sol = solve_fixed_order(inp, order, s.weights, s.min_buffer)
            if sol is None:
                continue
            c = compute_cost(inp, sol.changes, s.weights)
            w = s.weights
            # The DP leaves out D_intent (not additive) and D_order (fixed order = 0), and
            # D_move is a difference to the original route, which is a constant for the DP.
            expected = (
                c.rc_total
                - w.w_intent * c.breakdown.d_intent
                - w.w_order * c.breakdown.d_order
                + w.w_move * original_route / 60
            )
            if abs(sol.cost - expected) > 1e-9:
                mismatches.append((seed, s.name, sol.cost, expected))
    assert not mismatches, mismatches[:5]


@pytest.mark.parametrize("seeds", SMALL_SEED_SETS)
def test_pruned_start_candidates_lose_nothing(seeds: range) -> None:
    worse = []
    for seed in seeds:
        inp = random_instance(seed, max_activities=4)
        order = _order(inp)
        for s in STRATEGIES:
            fast = solve_fixed_order(inp, order, s.weights, s.min_buffer)
            full = solve_fixed_order(inp, order, s.weights, s.min_buffer, dense_starts=True)
            assert (fast is None) == (full is None), (seed, s.name)
            if fast is not None and fast.cost > full.cost + 1e-9:
                worse.append((seed, s.name, round(fast.cost, 4), round(full.cost, 4)))
    assert not worse, worse[:5]


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_solver_ms_is_not_set_by_the_engine(seed: int) -> None:
    for result in recover(random_instance(seed)):
        assert result.solver_ms == 0


def test_twelve_short_activities_solve_in_about_a_second() -> None:
    import time

    slowest = 0.0
    for seed in range(5):
        inp = random_instance(seed, max_activities=12, length_units=(3, 5))
        assert len(inp.activities) >= 10, len(inp.activities)
        started = time.perf_counter()
        solve_fixed_order(inp, _order(inp))
        slowest = max(slowest, time.perf_counter() - started)
    print(f"slowest single solve: {slowest:.2f}s")
    assert slowest < 2.0  # CLAUDE.md target is < 1s; this guards against blow-ups
