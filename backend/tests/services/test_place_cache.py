from datetime import UTC, datetime, timedelta
from typing import Any

from app.schemas.place import Place
from app.services.place_cache import (
    COORD_TTL,
    get_places,
    is_fresh,
    missing_ids,
    purge_expired,
    save_places,
)

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


class FakeTable:
    """Just enough of supabase's query builder for the calls place_cache makes."""

    def __init__(self, rows: dict[str, dict[str, Any]]) -> None:
        self.rows = rows
        self.queries = 0
        self._ids: list[str] | None = None
        self._upsert: list[dict[str, Any]] | None = None
        self._update: dict[str, Any] | None = None
        self._before: str | None = None

    def select(self, _columns: str) -> "FakeTable":
        return self

    def in_(self, _column: str, ids: list[str]) -> "FakeTable":
        self._ids = ids
        return self

    def upsert(self, rows: list[dict[str, Any]], on_conflict: str) -> "FakeTable":
        assert on_conflict == "place_id"
        self._upsert = rows
        return self

    def update(self, values: dict[str, Any]) -> "FakeTable":
        self._update = values
        return self

    def lt(self, column: str, value: str) -> "FakeTable":
        assert column == "fetched_at"
        self._before = value
        return self

    def execute(self) -> Any:
        self.queries += 1
        if self._upsert is not None:
            for row in self._upsert:
                self.rows[row["place_id"]] = row
            return type("R", (), {"data": self._upsert})()
        if self._update is not None:
            for row in self.rows.values():
                if row["fetched_at"] < self._before:  # ISO strings in one zone sort correctly
                    row.update(self._update)
            return type("R", (), {"data": []})()
        found = [self.rows[i] for i in self._ids or [] if i in self.rows]
        return type("R", (), {"data": found})()


class FakeClient:
    def __init__(self, rows: dict[str, dict[str, Any]] | None = None) -> None:
        self.table_ = FakeTable(rows or {})

    def table(self, _name: str) -> FakeTable:
        return self.table_


def _row(pid: str, age: timedelta, lat: float | None = 1.0) -> dict[str, Any]:
    return {
        "place_id": pid,
        "lat": lat,
        "lng": 2.0 if lat is not None else None,
        "fetched_at": (NOW - age).isoformat(),
    }


def _place(pid: str) -> Place:
    return Place(place_id=pid, lat=48.85, lng=2.35)


def test_get_places_returns_only_cached_ids() -> None:
    client = FakeClient({"a": _row("a", timedelta(days=1))})
    got = get_places(client, ["a", "b"], NOW)  # type: ignore[arg-type]
    assert set(got) == {"a"}


def test_get_places_with_no_ids_does_not_query() -> None:
    client = FakeClient()
    assert get_places(client, [], NOW) == {}  # type: ignore[arg-type]
    assert client.table_.queries == 0


def test_coordinates_older_than_the_limit_count_as_missing() -> None:
    client = FakeClient(
        {
            "fresh": _row("fresh", COORD_TTL - timedelta(minutes=1)),
            "stale": _row("stale", COORD_TTL),
        }
    )
    got = get_places(client, ["fresh", "stale"], NOW)  # type: ignore[arg-type]
    assert set(got) == {"fresh"}
    assert missing_ids(got, ["fresh", "stale"]) == ["stale"]


def test_the_limit_is_inside_googles_thirty_days() -> None:
    assert COORD_TTL < timedelta(days=30)


def test_row_without_coordinates_is_missing_not_fresh() -> None:
    place = Place(place_id="a", lat=None, lng=None, fetched_at=NOW)
    assert is_fresh(place, NOW) is False


def test_missing_ids_is_sorted_and_deduplicated() -> None:
    cached = {"a": _place("a")}
    assert missing_ids(cached, ["c", "a", "b", "c"]) == ["b", "c"]


def test_save_then_get_round_trips_and_stamps_fetched_at() -> None:
    client = FakeClient()
    save_places(client, [_place("b"), _place("a")], NOW)  # type: ignore[arg-type]
    assert list(client.table_.rows) == ["a", "b"]  # written in sorted order
    got = get_places(client, ["a", "b"], NOW)  # type: ignore[arg-type]
    assert got["a"].fetched_at == NOW


def test_saved_rows_hold_only_what_the_policy_allows() -> None:
    client = FakeClient()
    save_places(client, [_place("a")], NOW)  # type: ignore[arg-type]
    assert set(client.table_.rows["a"]) == {"place_id", "lat", "lng", "fetched_at"}


def test_save_places_with_nothing_does_not_write() -> None:
    client = FakeClient()
    save_places(client, [], NOW)  # type: ignore[arg-type]
    assert client.table_.queries == 0


def test_purge_nulls_expired_coordinates_and_keeps_the_place_id() -> None:
    client = FakeClient(
        {"old": _row("old", COORD_TTL + timedelta(days=1)), "new": _row("new", timedelta(days=1))}
    )
    purge_expired(client, NOW)  # type: ignore[arg-type]
    rows = client.table_.rows
    assert rows["old"]["lat"] is None and rows["old"]["lng"] is None
    assert "old" in rows  # the place_id stays
    assert rows["new"]["lat"] == 1.0
