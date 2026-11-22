"""Limit 7 (2026-11-22): a candidate the validator rejects is reported, not silently lost.

CLAUDE.md 6: "violation -> discard the candidate (+ log)". The engine stays pure: it hands the
rejected candidates back as values and the service layer writes the log. The solver normally
never produces a violating plan, so these tests force one.
"""

import logging

from app.engine import candidate
from app.engine.optimizer_dp import Solution
from app.engine.presets import STRATEGIES
from app.engine.recover import recover
from app.schemas.enums import Op
from app.schemas.recovery import RecoveryChange, Slot
from app.services.recovery_service import run_recovery
from tests.engine.helpers import load_scenario_a


def _broken_solver(inp, order, weights, min_buffer, **_rules):
    """Keeps everything as planned: in scenario A (2 h late) the morning is then in the past."""
    changes = tuple(
        RecoveryChange(
            activity_id=a.id,
            op=Op.KEEP,
            before=Slot(start=a.planned_start, end=a.planned_end),
            after=Slot(start=a.planned_start, end=a.planned_end),
        )
        for a in inp.activities
    )
    return Solution(changes, 0.0)


def test_rejected_candidates_are_handed_back_with_their_violations(monkeypatch) -> None:
    monkeypatch.setattr(candidate, "solve_fixed_order", _broken_solver)
    discards: list = []
    assert recover(load_scenario_a(), max_tries=0, discards=discards) == []
    assert [d.strategy for d in discards] == [s.name for s in STRATEGIES]
    assert all(any(v.kind == "past" for v in d.violations) for d in discards)


def test_nothing_is_reported_when_every_candidate_passes() -> None:
    discards: list = []
    assert recover(load_scenario_a(), discards=discards)
    assert discards == []


def test_the_service_logs_each_rejected_candidate(monkeypatch, caplog) -> None:
    monkeypatch.setattr(candidate, "solve_fixed_order", _broken_solver)
    with caplog.at_level(logging.WARNING, logger="app.services.recovery_service"):
        response = run_recovery(load_scenario_a())
    assert response.candidates == ()
    logged = [r for r in caplog.records if "validator rejected" in r.getMessage()]
    assert len(logged) == len(STRATEGIES)
    assert "balanced" in logged[0].getMessage() and "past" in logged[0].getMessage()
