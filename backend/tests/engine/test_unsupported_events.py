import pytest

from app.engine.candidate import UnsupportedEventError
from app.engine.recover import recover
from tests.engine.helpers import scenario_a_with_unsupported_event

UNSUPPORTED = ["RESERVATION_CHANGE", "MUST_VISIT"]


@pytest.mark.parametrize("kind", UNSUPPORTED)
def test_an_event_the_engine_cannot_handle_is_refused_not_ignored(kind: str) -> None:
    # Before this guard RESERVATION_CHANGE came back as the original plan ("0 violations,
    # 100% preserved") and MUST_VISIT as "no plan": a wrong answer, silently.
    inp = scenario_a_with_unsupported_event(kind)
    with pytest.raises(UnsupportedEventError, match=kind):
        recover(inp)
