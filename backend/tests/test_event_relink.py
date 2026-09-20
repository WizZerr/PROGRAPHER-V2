from pathlib import Path

from app.catalog.event_store import EventStore
from app.services.event_service import (
    event_availability,
    open_event_folder,
    relink_event,
)


def test_missing_root_is_reported(tmp_path: Path) -> None:
    original = tmp_path / "אירוע"
    original.mkdir()
    (original / "A.CR3").write_bytes(b"A" * 1024)

    store = EventStore(tmp_path / "state.sqlite3")
    opened = open_event_folder(str(original), store=store)

    moved = tmp_path / "אירוע-הועבר"
    original.rename(moved)

    availability = event_availability(opened.event.id, store=store)

    assert availability.root_exists is False
    assert availability.missing_files == 1


def test_relink_preserves_event_identity(tmp_path: Path) -> None:
    original = tmp_path / "event"
    original.mkdir()
    (original / "A.NEF").write_bytes(b"A" * 1024)
    (original / "B.NEF").write_bytes(b"B" * 1024)

    store = EventStore(tmp_path / "state.sqlite3")
    opened = open_event_folder(str(original), store=store)

    moved = tmp_path / "event-moved"
    original.rename(moved)

    result = relink_event(opened.event.id, str(moved), store=store)

    assert result.event.id == opened.event.id
    assert result.event.root_path == str(moved.resolve())
    assert result.matched_files == 2
    assert result.missing_files == 0


def test_relink_rejects_unrelated_folder(tmp_path: Path) -> None:
    original = tmp_path / "event"
    original.mkdir()
    (original / "A.NEF").write_bytes(b"A" * 1024)

    unrelated = tmp_path / "wrong"
    unrelated.mkdir()
    (unrelated / "X.NEF").write_bytes(b"X" * 1024)

    store = EventStore(tmp_path / "state.sqlite3")
    opened = open_event_folder(str(original), store=store)

    try:
        relink_event(opened.event.id, str(unrelated), store=store)
    except ValueError:
        return

    raise AssertionError("unrelated folder should not be accepted")
