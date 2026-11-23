from app.llm.parser import ParsedDay, ParsedItem, ParsedItinerary
from app.services.itinerary_draft import build_draft


def _item(title, start=None, end=None, role="activity", note=None) -> ParsedItem:
    return ParsedItem(
        title=title,
        start=start,
        end=end,
        category="sightseeing",
        role=role,
        reserved=False,
        note=note,
        place_query=None,
        address=None,
        within=None,
        spot=None,
        patch=None,
    )


def test_a_remark_line_becomes_a_note_of_the_place_above_not_an_item():
    # The Prague paste (2026-11-23): "※ ...한 곳만 방문한다." stood as an item with no time.
    remark = "※ 입국이 지연되면 구시가지 광장과 카를교 중 한 곳만 방문한다."
    day = ParsedDay(
        day_label="DAY 1",
        theme=None,
        items=[
            _item("관광: Charles Bridge", "21:00", "21:30", note="활동: 야경"),
            _item("호텔 복귀 및 휴식", "21:30", "22:00", role="lodging"),
            _item(remark),
        ],
    )
    draft = build_draft(ParsedItinerary(days=[day]))
    titles = [i.title for i in draft.days[0].items]
    assert remark not in titles
    bridge = next(i for i in draft.days[0].items if "Charles" in i.title)
    assert bridge.note == f"활동: 야경\n{remark}"
    assert not any(x.code == "NO_TIME" for x in draft.days[0].issues)


def test_an_untimed_place_is_still_an_item():
    day = ParsedDay(
        day_label=None,
        theme=None,
        items=[_item("하라주쿠", "10:00", "11:00"), _item("메이지 신궁")],
    )
    draft = build_draft(ParsedItinerary(days=[day]))
    assert [i.title for i in draft.days[0].items] == ["하라주쿠", "메이지 신궁"]
