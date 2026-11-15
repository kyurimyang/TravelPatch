from app.llm.disruption_interpreter import SYSTEM_PROMPT, InterpretedDisruption, interpret


class FakeProvider:
    """Records the call and returns a canned interpretation."""

    def __init__(self, answer: InterpretedDisruption) -> None:
        self.answer = answer
        self.seen: dict = {}

    def complete_json(self, *, system, user, schema):
        self.seen = {"system": system, "user": user, "schema": schema}
        return self.answer


def _blank(**fields) -> InterpretedDisruption:
    base = {
        "type": "UNKNOWN",
        "delay_minutes": None,
        "time_from": None,
        "time_to": None,
        "activity_hint": None,
        "extra_minutes": None,
        "new_time": None,
    }
    return InterpretedDisruption(**{**base, **fields})


def test_passes_text_and_schema_to_provider():
    provider = FakeProvider(_blank(type="DELAY", delay_minutes=120))
    result = interpret(provider, "  늦잠 잤어 2시간  ")
    assert result.type == "DELAY" and result.delay_minutes == 120
    assert provider.seen["user"] == "늦잠 잤어 2시간"
    assert provider.seen["system"] == SYSTEM_PROMPT
    assert provider.seen["schema"] is InterpretedDisruption


def test_every_event_type_is_covered_by_the_schema():
    from app.schemas.enums import EventType

    allowed = set(InterpretedDisruption.model_fields["type"].annotation.__args__)
    assert {e.value for e in EventType} <= allowed
