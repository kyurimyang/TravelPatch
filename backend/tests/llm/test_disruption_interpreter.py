from typing import get_args

from app.llm.disruption_interpreter import (
    SYSTEM_PROMPT,
    EventKind,
    InterpretedDisruption,
    InterpretedMessage,
    WishKind,
    interpret,
)


class FakeProvider:
    """Records the call and returns a canned interpretation."""

    def __init__(self, answer: InterpretedMessage) -> None:
        self.answer = answer
        self.seen: dict = {}

    def complete_json(self, *, system, user, schema):
        self.seen = {"system": system, "user": user, "schema": schema}
        return self.answer


def _event(**fields) -> InterpretedDisruption:
    base = dict.fromkeys(InterpretedDisruption.model_fields)
    return InterpretedDisruption(**{**base, "type": "UNKNOWN", **fields})


def test_passes_text_and_schema_to_provider():
    answer = InterpretedMessage(events=[_event(type="DELAY", delay_minutes=120)], wishes=[])
    provider = FakeProvider(answer)
    result = interpret(provider, "  늦잠 잤어 2시간  ")
    assert result.events[0].type == "DELAY" and result.events[0].delay_minutes == 120
    assert provider.seen["user"] == "늦잠 잤어 2시간"
    assert provider.seen["system"] == SYSTEM_PROMPT
    assert provider.seen["schema"] is InterpretedMessage


def test_every_event_type_is_covered_by_the_schema():
    from app.schemas.enums import EventType

    assert {e.value for e in EventType} <= set(get_args(EventKind))


def test_every_wish_is_covered_by_the_schema():
    from app.schemas.enums import Wish

    assert {w.value for w in Wish} == set(get_args(WishKind))


def test_every_field_is_required_for_structured_output():
    # OpenAI strict mode: each property must be listed as required (nullable, no default).
    schema = InterpretedDisruption.model_json_schema()
    assert set(schema["required"]) == set(InterpretedDisruption.model_fields)
