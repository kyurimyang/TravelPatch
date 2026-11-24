from typing import get_args

import pytest

from app.llm.parser import (
    MAX_TEXT_CHARS,
    PATCH_KINDS,
    SYSTEM_PROMPT,
    ParsedDay,
    ParsedItem,
    ParsedItinerary,
    Role,
    TextTooLongError,
    parse_itinerary,
)


class FakeProvider:
    def __init__(self, answer: ParsedItinerary) -> None:
        self.answer = answer
        self.calls = 0
        self.seen: dict = {}

    def complete_json(self, *, system, user, schema):
        self.calls += 1
        self.seen = {"system": system, "user": user, "schema": schema}
        return self.answer


def _item(title: str, **fields) -> ParsedItem:
    base = {
        "title": title,
        "start": None,
        "end": None,
        "category": "other",
        "reserved": False,
        "note": None,
        "place_query": None,
        "patch": None,
        "role": "activity",
        "address": None,
        "within": None,
        "spot": None,
    }
    return ParsedItem(**{**base, **fields})


def test_passes_trimmed_text_and_schema_to_provider():
    answer = ParsedItinerary(
        days=[ParsedDay(day_label="1일차", theme=None, items=[_item("센소지", start="09:00")])]
    )
    provider = FakeProvider(answer)
    result = parse_itinerary(provider, "  1일차\n09:00 센소지  ")
    assert result == answer
    assert provider.seen["user"] == "1일차\n09:00 센소지"
    assert provider.seen["system"] == SYSTEM_PROMPT
    assert provider.seen["schema"] is ParsedItinerary


def test_too_long_text_is_refused_before_calling_the_llm():
    provider = FakeProvider(ParsedItinerary(days=[]))
    with pytest.raises(TextTooLongError):
        parse_itinerary(provider, "가" * (MAX_TEXT_CHARS + 1))
    assert provider.calls == 0


def test_text_at_the_limit_is_accepted():
    provider = FakeProvider(ParsedItinerary(days=[]))
    parse_itinerary(provider, "가" * MAX_TEXT_CHARS)
    assert provider.calls == 1


def test_category_outside_the_list_is_rejected_by_the_schema():
    with pytest.raises(ValueError):
        _item("x", category="museum")


def test_patch_kind_from_the_list_is_accepted():
    assert _item("x", patch="museum").patch == "museum"


def test_patch_kind_outside_the_list_is_rejected_by_the_schema():
    with pytest.raises(ValueError):
        _item("x", patch="spaceport")


def test_every_patch_kind_is_named_in_the_prompt():
    for kind in PATCH_KINDS:
        assert kind in SYSTEM_PROMPT


def test_role_outside_the_list_is_rejected_by_the_schema():
    with pytest.raises(ValueError):
        _item("x", role="meal")


def test_every_role_is_named_in_the_prompt():
    for role in get_args(Role):
        assert role in SYSTEM_PROMPT
