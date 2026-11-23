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


def test_each_signed_in_user_has_their_own_limit() -> None:
    q = GuestQuota(
        {Kind.LLM: Limit(per_ip=1, total=1, per_user=2), Kind.PLACES: SMALL[Kind.PLACES]}
    )
    assert [q.charge_user(Kind.LLM, "u1") for _ in range(3)] == [True, True, False]
    assert q.charge_user(Kind.LLM, "u2")
    assert q.charge(Kind.LLM, "1.1.1.1")  # users do not use up the guests' total


class _Store:
    def __init__(self, answer: bool | None) -> None:
        self.answer = answer
        self.calls: list[tuple] = []

    def charge(self, kind, subject, limit, total_subject, total_limit) -> bool:
        self.calls.append((kind, subject, limit, total_subject, total_limit))
        if self.answer is None:
            raise ConnectionError("db down")
        return self.answer


def test_the_database_store_decides_when_present() -> None:
    store = _Store(False)
    q = GuestQuota(SMALL, store=store)
    assert not q.charge(Kind.LLM, "1.1.1.1")
    assert store.calls == [(Kind.LLM, "ip:1.1.1.1", 2, "guests", 3)]
    q.charge_user(Kind.LLM, "u1")
    assert store.calls[-1][1:4] == ("user:u1", 100, None)  # SMALL has no per_user: the default


def test_an_unreachable_store_falls_back_to_memory() -> None:
    q = GuestQuota(SMALL, store=_Store(None))
    assert [q.charge(Kind.LLM, "a") for _ in range(3)] == [True, True, False]


def test_the_store_is_off_unless_asked_for(monkeypatch) -> None:
    from app.services.guest_quota import store_from_env

    monkeypatch.delenv("QUOTA_STORE", raising=False)
    assert store_from_env() is None


def test_a_guest_ip_never_reaches_the_database_as_is() -> None:
    from app.services.guest_quota import SupabaseUsageStore, pseudonymize

    class _Rpc:
        def __init__(self) -> None:
            self.params: dict = {}

        def rpc(self, name, params):
            self.params = params
            return self

        def execute(self):
            return type("R", (), {"data": True})()

    db = _Rpc()
    assert SupabaseUsageStore(db, "k").charge(Kind.LLM, "ip:203.0.113.7", 2, "guests", 3)
    assert "203.0.113.7" not in db.params["p_subject"]
    assert db.params["p_subject"] == pseudonymize("ip:203.0.113.7", "k")
    assert pseudonymize("ip:203.0.113.7", "other key") != db.params["p_subject"]
    assert pseudonymize("user:u1", "k") == "user:u1"  # deleted by id on withdrawal
