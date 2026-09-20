from pathlib import Path

from app.catalog.event_store import EventStore
from app.services.event_service import open_event_folder, relink_event


def test_rescan_after_relink_reuses_original_event_id(tmp_path: Path) -> None:
    original = tmp_path / "event"
    original.mkdir()
    (original / "A.CR3").write_bytes(b"A" * 2048)
    (original / "B.CR3").write_bytes(b"B" * 2048)

    store = EventStore(tmp_path / "state.sqlite3")

    first = open_event_folder(str(original), store=store)
    original_id = first.event.id

    moved = tmp_path / "event-moved"
    original.rename(moved)

    relinked = relink_event(original_id, str(moved), store=store)
    assert relinked.event.id == original_id

    rescanned = open_event_folder(str(moved), store=store)

    assert rescanned.event.id == original_id
    assert rescanned.result == "existing"
    assert rescanned.new_files_added == 0
    assert len(store.list_events()) == 1
