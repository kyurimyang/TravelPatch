from datetime import date

from app.services.guest_quota import GuestQuota, Kind, Limit

SMALL = {Kind.LLM: Limit(per_ip=2, total=3), Kind.PLACES: Limit(per_ip=1, total=1)}


def _quota(day: list[date]) -> GuestQuota:
    return GuestQuota(SMALL, today=lambda: day[0])


def test_per_ip_limit() -> None:
    q = _quota([date(2026, 11, 22)])
    assert [q.charge(Kind.LLM, "1.1.1.1") for _ in range(3)] == [True, True, False]
    assert q.charge(Kind.LLM, "2.2.2.2")  # another guest is not affected


def test_total_limit_holds_across_ips() -> None:
    q = _quota([date(2026, 11, 22)])
    allowed = [q.charge(Kind.LLM, f"10.0.0.{i}") for i in range(5)]
    assert allowed == [True, True, True, False, False]  # forged IPs do not raise the ceiling


def test_refused_calls_are_not_counted() -> None:
    q = GuestQuota({Kind.LLM: Limit(per_ip=1, total=2), Kind.PLACES: SMALL[Kind.PLACES]})
    assert q.charge(Kind.LLM, "a")
    assert not q.charge(Kind.LLM, "a")  # refused: the total stays at 1
    assert q.charge(Kind.LLM, "b")


def test_kinds_are_counted_apart() -> None:
    q = _quota([date(2026, 11, 22)])
    assert q.charge(Kind.PLACES, "a")
    assert not q.charge(Kind.PLACES, "a")
    assert q.charge(Kind.LLM, "a")


def test_new_day_starts_again() -> None:
    day = [date(2026, 11, 22)]
    q = _quota(day)
    assert q.charge(Kind.PLACES, "a")
    assert not q.charge(Kind.PLACES, "a")
    day[0] = date(2026, 11, 23)
    assert q.charge(Kind.PLACES, "a")
