import pytest

from app.engine.candidate import UnsupportedEventError
from app.engine.recover import recover
from tests.engine.helpers import scenario_a_with_unsupported_event

# RESERVATION_CHANGE is supported since 2026-11-22 (scenario F).
UNSUPPORTED = ["MUST_VISIT"]


@pytest.mark.parametrize("kind", UNSUPPORTED)
def test_an_event_the_engine_cannot_handle_is_refused_not_ignored(kind: str) -> None:
    # Before this guard RESERVATION_CHANGE came back as the original plan ("0 violations,
    # 100% preserved") and MUST_VISIT as "no plan": a wrong answer, silently.
    inp = scenario_a_with_unsupported_event(kind)
    with pytest.raises(UnsupportedEventError, match=kind):
        recover(inp)


def test_reservation_change_is_solved_now() -> None:
    # The guard above used to cover it; it must now come back as real candidates.
    results = recover(scenario_a_with_unsupported_event("RESERVATION_CHANGE"))
    assert results
    assert all(r.violations == 0 for r in results)
