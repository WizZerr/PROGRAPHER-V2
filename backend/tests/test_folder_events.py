from __future__ import annotations

import hashlib
from pathlib import Path

from app.catalog.event_store import EventStore
from app.services.event_service import open_event_folder


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_unicode_folder_scan_is_read_only_and_persistent(tmp_path: Path) -> None:
    folder = tmp_path / "חתונה - יעל ועומר"
    folder.mkdir()

    raw = folder / "DSC_0001.CR3"
    jpg = folder / "תמונה ערוכה.JPG"
    ignored = folder / "notes.txt"

    raw.write_bytes(b"RAW" * 1000)
    jpg.write_bytes(b"JPEG" * 500)
    ignored.write_text("ignore me", encoding="utf-8")

    before_raw = digest(raw)
    before_jpg = digest(jpg)

    store = EventStore(tmp_path / "state" / "test.sqlite3")

    result = open_event_folder(str(folder), store=store)

    assert result.result == "created"
    assert result.event.name == "חתונה - יעל ועומר"
    assert result.event.total_files == 2
    assert result.event.raw_files == 1
    assert result.event.rendered_files == 1
    assert result.duplicate_files_ignored == 0

    assert digest(raw) == before_raw
    assert digest(jpg) == before_jpg

    listed = store.list_events()
    assert len(listed) == 1
    assert listed[0].id == result.event.id


def test_reopening_same_folder_is_reported_as_existing(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "event"
    folder.mkdir()

    (folder / "A.NEF").write_bytes(b"A" * 1024)
    (folder / "B.NEF").write_bytes(b"B" * 1024)

    store = EventStore(tmp_path / "state.sqlite3")

    first = open_event_folder(str(folder), store=store)
    second = open_event_folder(str(folder), store=store)

    assert first.result == "created"
    assert second.result == "existing"
    assert second.new_files_added == 0
    assert first.event.id == second.event.id
    assert second.event.total_files == 2
    assert len(store.list_events()) == 1


def test_existing_event_with_new_file_is_reported_as_updated(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "event"
    folder.mkdir()
    (folder / "A.NEF").write_bytes(b"A" * 1024)

    store = EventStore(tmp_path / "state.sqlite3")
    open_event_folder(str(folder), store=store)

    (folder / "B.NEF").write_bytes(b"B" * 1024)
    result = open_event_folder(str(folder), store=store)

    assert result.result == "updated"
    assert result.new_files_added == 1
    assert result.event.total_files == 2


def test_identical_duplicate_file_is_counted_once(tmp_path: Path) -> None:
    folder = tmp_path / "event"
    folder.mkdir()

    payload = b"same-photo-bytes" * 100
    (folder / "A.CR3").write_bytes(payload)
    (folder / "A-copy.CR3").write_bytes(payload)

    store = EventStore(tmp_path / "state.sqlite3")
    result = open_event_folder(str(folder), store=store)

    assert result.event.total_files == 1
    assert result.event.raw_files == 1
    assert result.duplicate_files_ignored == 1
