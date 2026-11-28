from app.llm.parser import ParsedDay, ParsedItem, ParsedItinerary
from app.services.itinerary_draft import DEFAULT_MINUTES, build_draft, unread_lines


def _item(title="x", **fields) -> ParsedItem:
    base = {
        "title": title,
        "start": None,
        "end": None,
        "category": "sightseeing",
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


def test_patch_kind_is_passed_through():
    item = _day(_item("메이지 신궁", start="09:00", patch="worship")).items[0]
    assert item.patch == "worship"


def test_no_patch_kind_stays_none():
    assert _day(_item("점심", start="12:00")).items[0].patch is None


def test_place_query_from_the_title_is_kept():
    item = _day(_item("오모테산도 산책", start="15:00", place_query="오모테산도")).items[0]
    assert item.place_query == "오모테산도"


def test_place_query_may_come_from_the_note_and_ignores_spacing():
    line = _item("점심", start="12:00", note="이치란 신주쿠점", place_query="이치란신주쿠점")
    item = _day(line).items[0]
    assert item.place_query == "이치란신주쿠점"


def test_place_query_not_written_in_the_line_is_dropped():
    # The model may not invent a restaurant for "점심 - 스시" (invariants 4 and 8).
    item = _day(_item("점심 - 스시", start="12:00", place_query="스시 잔마이")).items[0]
    assert item.place_query is None


def test_blank_place_query_is_none():
    assert _day(_item("산책", start="15:00", place_query="  ")).items[0].place_query is None


def _day(*items: ParsedItem):
    return build_draft(
        ParsedItinerary(days=[ParsedDay(day_label="1일차", theme=None, items=list(items))])
    ).days[0]


def _codes(day) -> list[str]:
    return [i.code for i in day.issues]


def test_times_become_minutes_and_a_complete_range_is_kept_as_written():
    day = _day(_item(start="09:00", end="10:30"))
    item = day.items[0]
    assert (item.start, item.end, item.duration_estimated) == (540, 630, False)
    assert day.issues == ()


def test_missing_end_uses_the_category_default_and_is_marked_estimated():
    for category, minutes in DEFAULT_MINUTES.items():
        item = _day(_item(start="10:00", category=category)).items[0]
        assert item.end == 600 + minutes and item.duration_estimated is True


def test_missing_start_is_not_guessed():
    day = _day(_item(end="11:00"))
    assert day.items[0].start is None and _codes(day) == ["MISSING_START"]


def test_no_time_at_all_is_an_issue_not_a_guess():
    day = _day(_item("저녁은 근처에서"))
    assert day.items[0].start is None and _codes(day) == ["NO_TIME"]


def test_bad_time_text_is_reported_and_not_converted():
    day = _day(_item(start="9시쯤"))
    assert day.items[0].start is None and _codes(day) == ["BAD_TIME"]


def test_end_not_after_start_is_flagged():
    assert _codes(_day(_item(start="12:00", end="11:00"))) == ["BAD_RANGE"]


def test_estimated_end_past_midnight_is_clamped_and_flagged():
    day = _day(_item(start="23:30", category="sightseeing"))
    assert day.items[0].end == 1440 and _codes(day) == ["OVER_MIDNIGHT"]


def test_reserved_item_holds_its_start_time():
    assert _day(_item(start="15:00", reserved=True)).items[0].reservation_time == 900


def test_reserved_without_a_time_is_flagged():
    assert "RESERVED_NO_TIME" in _codes(_day(_item(reserved=True)))


def test_order_and_overlap_are_flagged_but_nothing_is_reordered():
    day = _day(
        _item("a", start="10:00", end="11:00"),
        _item("b", start="10:30", end="11:30"),
        _item("c", start="09:00", end="09:30"),
    )
    assert [i.title for i in day.items] == ["a", "b", "c"]
    assert [(i.item, i.code) for i in day.issues] == [(1, "OVERLAP"), (2, "OUT_OF_ORDER")]


def test_untimed_item_between_timed_ones_does_not_hide_an_overlap():
    day = _day(
        _item("a", start="10:00", end="12:00"),
        _item("free"),
        _item("b", start="11:00", end="11:30"),
    )
    assert ("OVERLAP", 2) in [(i.code, i.item) for i in day.issues]


def test_same_input_gives_the_same_draft():
    parsed = ParsedItinerary(
        days=[ParsedDay(day_label=None, theme=None, items=[_item(start="08:00")])]
    )
    assert build_draft(parsed) == build_draft(parsed)


# ---- a time the model left out is taken back from the text ----


def _draft_with(text: str, *items: ParsedItem):
    parsed = ParsedItinerary(days=[ParsedDay(day_label="DAY 1", theme=None, items=list(items))])
    return build_draft(parsed, text).days[0]


def test_untimed_block_takes_the_time_written_on_its_own_line():
    """Busan live test 2026-11-28: "20:00~ · 숙소 이동 및 휴식" came back with no time, so day 1
    had no end at the hotel. The 20:00 is written on that line: it is restored."""
    text = "DAY 1\n* 19:00~20:00 · 야경 감상 — 부산타워\n* 20:00~ · 숙소 이동 및 휴식\n"
    day = _draft_with(
        text,
        _item("야경 감상 — 부산타워", start="19:00", end="20:00"),
        _item("숙소 이동 및 휴식", role="lodging", category="other"),
    )
    assert day.end_time == 20 * 60


def test_untimed_block_never_takes_a_later_line_that_only_mentions_it():
    """Only the next unread time line counts: "쇼핑" with no time stays untimed even though a
    later line says "아키하바라 쇼핑" (invariant 8: no time is moved from another block)."""
    text = "09:00 센소지\n쇼핑\n12:00 점심\n14:00-16:00 아키하바라 쇼핑\n"
    day = _draft_with(
        text,
        _item("센소지", start="09:00"),
        _item("쇼핑"),
        _item("점심", start="12:00", category="meal"),
        _item("아키하바라 쇼핑", start="14:00", end="16:00", category="shopping"),
    )
    assert [(i.title, i.start) for i in day.items] == [
        ("센소지", 540),
        ("쇼핑", None),
        ("점심", 720),
        ("아키하바라 쇼핑", 840),
    ]


def test_unread_lines_names_exactly_the_dropped_time_line():
    """One dropped line out of many is found (the old 80% bar let it through silently), named as
    written; a line whose time was only left out of the answer is not unread."""
    text = (
        "* 09:00~10:00 · 아침\n* 10:00~11:00 · 산책\n* 11:00~12:00 · 점심\n* 12:00~ · 숙소 휴식\n"
    )
    parsed = ParsedItinerary(
        days=[
            ParsedDay(
                day_label=None,
                theme=None,
                items=[
                    _item("아침", start="09:00", end="10:00"),
                    _item("점심", start="11:00", end="12:00"),
                    _item("숙소 휴식", role="lodging"),
                ],
            )
        ]
    )
    assert unread_lines(parsed, text) == ["* 10:00~11:00 · 산책"]


def test_a_show_holds_its_start_time_even_without_the_word_reserved():
    """User test 2026-11-28: a Broadway musical at 19:30 was moved to 19:15. A venue (theater,
    concert, stadium, show) with a start time is held like a reservation."""
    show = _day(_item("브로드웨이 뮤지컬 관람", start="19:30", end="22:00", patch="venue")).items[0]
    assert show.reservation_time == 19 * 60 + 30


def test_a_venue_without_a_time_is_not_held_and_not_flagged_as_reserved():
    day = _day(_item("공연장 구경", patch="venue"))
    assert day.items[0].reservation_time is None
    assert "RESERVED_NO_TIME" not in _codes(day)
