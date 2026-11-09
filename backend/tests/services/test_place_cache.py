from typing import Any

from app.schemas.place import Place
from app.services.place_cache import get_places, missing_ids, save_places


class FakeTable:
    """Just enough of supabase's query builder: select().in_().execute() and upsert().execute()."""

    def __init__(self, rows: dict[str, dict[str, Any]]) -> None:
        self.rows = rows
        self.queries = 0
        self._ids: list[str] | None = None
        self._upsert: list[dict[str, Any]] | None = None

    def select(self, _columns: str) -> "FakeTable":
        return self

    def in_(self, _column: str, ids: list[str]) -> "FakeTable":
        self._ids = ids
        return self

    def upsert(self, rows: list[dict[str, Any]], on_conflict: str) -> "FakeTable":
        assert on_conflict == "place_id"
        self._upsert = rows
        return self

    def execute(self) -> Any:
        self.queries += 1
        if self._upsert is not None:
            for row in self._upsert:
                self.rows[row["place_id"]] = row
            return type("R", (), {"data": self._upsert})()
        found = [self.rows[i] for i in self._ids or [] if i in self.rows]
        return type("R", (), {"data": found})()


class FakeClient:
    def __init__(self, rows: dict[str, dict[str, Any]] | None = None) -> None:
        self.table_ = FakeTable(rows or {})

    def table(self, _name: str) -> FakeTable:
        return self.table_


def _place(pid: str, hours: dict[str, Any] | None = None) -> Place:
    return Place(
        place_id=pid, name=f"name-{pid}", lat=48.85, lng=2.35, opening_hours=hours
    )


def test_get_places_returns_only_cached_ids() -> None:
    client = FakeClient({"a": {"place_id": "a", "name": "A", "lat": 1.0, "lng": 2.0}})
    got = get_places(client, ["a", "b"])  # type: ignore[arg-type]
    assert set(got) == {"a"}
    assert got["a"].opening_hours is None  # unknown stays unknown, never "always open"


def test_get_places_with_no_ids_does_not_query() -> None:
    client = FakeClient()
    assert get_places(client, []) == {}  # type: ignore[arg-type]
    assert client.table_.queries == 0


def test_missing_ids_is_sorted_and_deduplicated() -> None:
    cached = {"a": _place("a")}
    assert missing_ids(cached, ["c", "a", "b", "c"]) == ["b", "c"]


def test_save_then_get_round_trips_and_stamps_fetched_at() -> None:
    client = FakeClient()
    save_places(client, [_place("b", {"periods": []}), _place("a")])  # type: ignore[arg-type]
    assert list(client.table_.rows) == ["a", "b"]  # written in sorted order
    got = get_places(client, ["a", "b"])  # type: ignore[arg-type]
    assert got["b"].opening_hours == {"periods": []}
    assert got["a"].fetched_at is not None


def test_save_places_with_nothing_does_not_write() -> None:
    client = FakeClient()
    save_places(client, [])  # type: ignore[arg-type]
    assert client.table_.queries == 0
