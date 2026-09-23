from __future__ import annotations

from pathlib import Path

from app.catalog.event_store import EventStore
from app.services.event_service import EventOpenError, list_event_files


class PreviewUnavailable(ValueError):
    pass


_READ_LIMIT = 32 * 1024 * 1024
_MIN_JPEG_BYTES = 800


def extract_embedded_jpeg(path: Path) -> bytes | None:
    """
    Return the largest JPEG embedded near the start of a camera file.

    The file is only read. This is a camera preview, not a Lightroom render.
    """
    with path.open("rb") as handle:
        blob = handle.read(_READ_LIMIT)

    best: bytes | None = None
    start = 0
    while True:
        marker = blob.find(b"\xff\xd8\xff", start)
        if marker < 0:
            break
        end = blob.find(b"\xff\xd9", marker + 3)
        if end < 0:
            break
        chunk = blob[marker : end + 2]
        if len(chunk) >= _MIN_JPEG_BYTES and (best is None or len(chunk) > len(best)):
            best = chunk
        start = marker + 2
        if best is not None and len(best) > 1_500_000:
            break
    return best


def camera_preview_bytes(event_id: str, fingerprint: str) -> bytes:
    store = EventStore()
    try:
        event = store.get_event(event_id)
        files = list_event_files(event_id, store)
    except (KeyError, EventOpenError) as exc:
        raise PreviewUnavailable("האירוע לא נמצא.") from exc

    match = next((item for item in files if item.fingerprint == fingerprint), None)
    if match is None:
        raise PreviewUnavailable("הקובץ לא נמצא באירוע.")

    root = Path(event.root_path).resolve()
    path = Path(match.absolute_path).resolve()
    if not path.is_file() or not path.is_relative_to(root):
        raise PreviewUnavailable("הקובץ אינו זמין בתוך תיקיית האירוע.")

    preview = extract_embedded_jpeg(path)
    if preview is None:
        raise PreviewUnavailable("אין תצוגת מצלמה בקובץ הזה.")
    return preview
