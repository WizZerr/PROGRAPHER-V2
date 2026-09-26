from __future__ import annotations

from pathlib import Path

from app.catalog.event_store import (
    EventAvailability,
    EventFile,
    EventOpenResult,
    EventStore,
    RelinkResult,
)
from app.ingest.scanner import FolderScanError, scan_event_folder


class EventOpenError(ValueError):
    pass


def open_event_folder(
    path: str,
    name: str | None = None,
    store: EventStore | None = None,
) -> EventOpenResult:
    event_store = store or EventStore()

    try:
        root = Path(path).expanduser().resolve(strict=True)
        sources = scan_event_folder(root)
    except (OSError, FolderScanError) as exc:
        raise EventOpenError(str(exc)) from exc

    return event_store.open_folder(root, sources, name=name)


def list_events(store: EventStore | None = None):
    return (store or EventStore()).list_events()


def list_event_files(
    event_id: str,
    store: EventStore | None = None,
) -> list[EventFile]:
    event_store = store or EventStore()
    try:
        return event_store.list_files(event_id)
    except KeyError as exc:
        raise EventOpenError("האירוע לא נמצא.") from exc


def delete_event(
    event_id: str,
    store: EventStore | None = None,
):
    event_store = store or EventStore()
    try:
        return event_store.delete_event(event_id)
    except KeyError as exc:
        raise EventOpenError("האירוע לא נמצא.") from exc


def event_availability(
    event_id: str,
    store: EventStore | None = None,
) -> EventAvailability:
    event_store = store or EventStore()
    try:
        return event_store.availability(event_id)
    except KeyError as exc:
        raise EventOpenError("האירוע לא נמצא.") from exc


def relink_event(
    event_id: str,
    path: str,
    store: EventStore | None = None,
) -> RelinkResult:
    event_store = store or EventStore()

    try:
        root = Path(path).expanduser().resolve(strict=True)
        sources = scan_event_folder(root)
        return event_store.relink_event(event_id, root, sources)
    except (OSError, FolderScanError, KeyError, ValueError) as exc:
        raise EventOpenError(str(exc)) from exc
