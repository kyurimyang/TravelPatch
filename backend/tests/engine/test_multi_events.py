"""Several events from one moment, stacked (decision 2026-11-26), and the "실내 우선" wish."""

from itertools import pairwise

import pytest
from pydantic import ValidationError

from app.engine.candidate import solve_candidate
from app.engine.cost import compute_cost
from app.engine.optimizer_dp import solve_fixed_order
from app.engine.presets import STRATEGIES, strategies_for
from app.engine.recover import original_order, recover
from app.engine.validator import validate
from app.schemas.enums import Op, Wish
from app.schemas.events import (
    ClosureEvent,
    DelayEvent,
    MustVisitEvent,
    ReservationChangeEvent,
    WaitEvent,
    WeatherEvent,
)
from app.schemas.models import Substitute
from app.schemas.recovery import RecoveryInput
from app.services.travel_estimate import fill_missing_travel
from tests.engine.helpers import load_scenario_a

NOW = 540  # 09:00 at the hotel, before the day starts


def _day(*more, wishes=(), event=None, **update) -> RecoveryInput:
    base = load_scenario_a()
    data = base.model_dump()
    data["event"] = (event or DelayEvent(occurred_at=NOW, start_time=NOW)).model_dump()
    data["more_events"] = [e.model_dump() for e in more]
    data["wishes"] = list(wishes)
    data.update(update)
    return RecoveryInput.model_validate(data)


def _with_sub(inp: RecoveryInput, outdoor: bool | None, substitutability: float = 0.2):
    """An indoor (or unknown) stand-in for harajuku, 300 m away."""
    sub = Substitute(
        id="sub_harajuku_1",
        replaces="harajuku",
        title="실내 전시",
        lat=35.6730,
        lng=139.7080,
        duration=60,
        min_duration=30,
        penalty=0.2,
        outdoor=outdoor,
    )
    points = {a.id: (a.lat, a.lng) for a in inp.activities}
    points |= {"hotel": (inp.day.end_lat, inp.day.end_lng), sub.id: (sub.lat, sub.lng)}
    prefs = [
        (
            p.model_copy(update={"substitutability": substitutability})
            if p.activity_id == "harajuku"
            else p
        )
        for p in inp.preferences
    ]
    return inp.model_copy(
        update={
            "substitutes": (sub,),
            "travel": fill_missing_travel(points, inp.travel),
            "preferences": tuple(prefs),
        }
    )


def _balanced(inp: RecoveryInput):
    result = solve_candidate(inp, STRATEGIES[0], original_order(inp))
    assert result is not None
    return {c.activity_id: c for c in result.changes}


# --- input checks ---------------------------------------------------------------------------


def test_single_event_input_is_unchanged():
    inp = load_scenario_a()
    assert inp.more_events == () and inp.wishes == () and inp.events == (inp.event,)


def test_events_must_share_the_moment_and_place():
    with pytest.raises(ValidationError, match="share"):
        _day(WeatherEvent(occurred_at=NOW + 5, start_time=600))
    with pytest.raises(ValidationError, match="share"):
        _day(WeatherEvent(occurred_at=NOW, start_time=600, location_id="meiji"))


def test_must_visit_only_as_the_main_event():
    extra = MustVisitEvent(
        occurred_at=NOW,
        activity_id="tower",
        title="도쿄타워",
        category="sightseeing",
        lat=35.65,
        lng=139.74,
        duration=60,
        min_duration=30,
    )
    with pytest.raises(ValidationError, match="main event"):
        _day(extra)


def test_two_bookings_for_one_piece_are_refused():
    a = ReservationChangeEvent(occurred_at=NOW, activity_id="sky", new_time=960)
    b = ReservationChangeEvent(occurred_at=NOW, activity_id="sky", new_time=900)
    with pytest.raises(ValidationError, match="two"):
        _day(a, b)


def test_now_is_the_latest_delay():
    late = DelayEvent(occurred_at=NOW, start_time=NOW + 90)
    assert _day(late).now == NOW + 90


# --- stacking -------------------------------------------------------------------------------


def test_every_event_is_applied_and_every_one_is_checked():
    rain = WeatherEvent(occurred_at=NOW, start_time=13 * 60)
    closed = ClosureEvent(occurred_at=NOW, activity_id="cafe")
    inp = _day(rain, closed)
    changes = _balanced(inp)
    assert changes["cafe"].op == Op.DROP  # closed, no substitute
    # A plan that only respects one of the two is caught for the other.
    broken = tuple(
        c.model_copy(update={"op": Op.KEEP, "after": c.before}) if c.activity_id == "cafe" else c
        for c in changes.values()
    )
    assert {v.kind for v in validate(inp, broken)} == {"closure"}


def test_rain_windows_from_two_events_both_hold():
    morning = WeatherEvent(occurred_at=NOW, start_time=550, end_time=600)
    later = WeatherEvent(occurred_at=NOW, start_time=700, end_time=760)
    for result in recover(_day(morning, later)):
        assert result.violations == 0
        meiji = next(c for c in result.changes if c.activity_id == "meiji")
        assert meiji.after is not None and meiji.after.start >= 600  # outdoor, after the rain


def test_a_booking_moved_earlier_and_a_queue_at_lunch_give_choices():
    sky = ReservationChangeEvent(occurred_at=NOW, activity_id="sky", new_time=13 * 60 + 30)
    queue = WaitEvent(occurred_at=NOW, activity_id="ramen", minutes=40)
    results = recover(_day(sky, queue))
    assert results, "the clash must be resolved, not refused"
    for r in results:
        by_id = {c.activity_id: c for c in r.changes}
        assert by_id["sky"].after.start == 13 * 60 + 30
        ramen = by_id["ramen"]
        assert ramen.after.end - ramen.after.start >= 40 + 40  # queue + shortest lunch
        assert ramen.after.end <= 13 * 60 + 30
    # Different candidates give up different things (what to cut is the user's choice).
    assert len({tuple((c.activity_id, c.op) for c in r.changes) for r in results}) > 1


def test_a_queue_too_short_in_the_plan_is_a_violation():
    queue = WaitEvent(occurred_at=NOW, activity_id="ramen", minutes=40)
    inp = _day(queue)
    plan = tuple(
        c.model_copy(update={"op": Op.KEEP, "after": c.before}) for c in _balanced(inp).values()
    )
    assert "wait" in {v.kind for v in validate(inp, plan)}


def test_a_queue_does_not_count_as_shrinking_or_growing_the_lunch():
    queue = WaitEvent(occurred_at=NOW, activity_id="ramen", minutes=40)
    inp = _day(queue)
    changes = tuple(_balanced(inp).values())
    ramen = next(c for c in changes if c.activity_id == "ramen")
    lunch = ramen.after.end - ramen.after.start - 40
    expected = 5 * max(0, 60 - lunch) / 60
    shrink_others = compute_cost(
        inp.model_copy(update={"more_events": ()}),
        tuple(c for c in changes if c.activity_id != "ramen")
        + (ramen.model_copy(update={"after": ramen.before}),),
    ).breakdown.d_shrink
    assert compute_cost(inp, changes).breakdown.d_shrink == pytest.approx(shrink_others + expected)


# --- indoor places and the wish -------------------------------------------------------------


def test_rain_can_send_an_outdoor_piece_to_a_known_indoor_place():
    rain = WeatherEvent(occurred_at=NOW, start_time=600, end_time=720)
    inp = _with_sub(_day(rain), outdoor=False)
    harajuku = _balanced(inp)["harajuku"]
    assert harajuku.op == Op.SUBSTITUTE and harajuku.substitute_id == "sub_harajuku_1"
    assert validate(inp, tuple(_balanced(inp).values())) == []


def test_rain_never_sends_it_to_a_place_of_unknown_kind():
    rain = WeatherEvent(occurred_at=NOW, start_time=600, end_time=720)
    inp = _with_sub(_day(rain), outdoor=None)  # read as the original: outdoors
    assert _balanced(inp)["harajuku"].op != Op.SUBSTITUTE


def test_indoor_wish_is_soft_and_only_counts_when_given():
    plain = _with_sub(_day(), outdoor=False, substitutability=0.8)
    wished = _with_sub(_day(wishes=[Wish.INDOOR]), outdoor=False, substitutability=0.8)
    assert _balanced(plain)["harajuku"].op != Op.SUBSTITUTE  # no wish: the day as planned
    assert _balanced(wished)["harajuku"].op == Op.SUBSTITUTE  # cheaper than staying outdoors
    # Soft: a piece with no indoor stand-in stays where it is (it is not dropped).
    assert _balanced(wished)["meiji"].op != Op.DROP
    changes = tuple(_balanced(plain).values())
    assert compute_cost(plain, changes).breakdown.d_outdoor == 0.0
    assert compute_cost(wished, changes).breakdown.d_outdoor > 0.0


@pytest.mark.parametrize("wait", [0, 40])
def test_cost_and_solver_agree(wait):
    # The DP adds the per-step terms itself; cost.py recomputes them from the slots. With the
    # wish (D_outdoor) and a queue (D_shrink without the queue) they must still match.
    more = (WaitEvent(occurred_at=NOW, activity_id="ramen", minutes=wait),) if wait else ()
    wished = _with_sub(_day(*more, wishes=[Wish.INDOOR]), outdoor=False, substitutability=0.8)
    solution = solve_fixed_order(wished, original_order(wished))
    cost = compute_cost(wished, solution.changes)
    assert cost.breakdown.d_order == 0 and cost.breakdown.d_intent == 0
    # The DP pays every travel leg; RC pays only the change from the original route.
    table = {frozenset((t.a, t.b)): t.minutes for t in wished.travel}
    order = original_order(wished)
    original = sum(table[frozenset(p)] for p in pairwise(order))
    offset = STRATEGIES[0].weights.w_move * original / 60
    assert solution.cost == pytest.approx(cost.rc_total + offset)


def test_rest_wish_puts_the_relaxed_candidate_first():
    assert strategies_for(()) == STRATEGIES
    order = strategies_for((Wish.REST,))
    assert order[0].name == "relaxed" and set(order) == set(STRATEGIES)


def test_more_events_are_deterministic():
    rain = WeatherEvent(occurred_at=NOW, start_time=13 * 60)
    queue = WaitEvent(occurred_at=NOW, activity_id="ramen", minutes=30)
    assert recover(_day(rain, queue)) == recover(_day(rain, queue))
