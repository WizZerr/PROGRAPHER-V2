from __future__ import annotations

from pathlib import Path

from app.catalog.event_store import EventStore
from app.platform.paths import user_data_dir
from app.services.event_service import EventOpenError, list_event_files


class PreviewUnavailable(ValueError):
    pass


_READ_LIMIT = 64 * 1024 * 1024
_MIN_JPEG_BYTES = 800
_JPEG_EXTENSIONS = {".jpg", ".jpeg"}
_CACHE_VERSION = "v2"
_MAX_PREVIEW_EDGE = 1800


def extract_embedded_jpeg(path: Path) -> bytes | None:
    """
    Fallback extractor for a JPEG preview embedded in a camera RAW.

    This never mutates the source. It is intentionally a fallback; supported
    RAW files are first offered to rawpy/LibRaw.
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
        if len(chunk) >= _MIN_JPEG_BYTES and (
            best is None or len(chunk) > len(best)
        ):
            best = chunk
        start = marker + 2
    return best


def _rawpy_preview(path: Path) -> bytes | None:
    try:
        import rawpy
    except ImportError:
        return None

    try:
        with rawpy.imread(str(path)) as raw:
            thumb = raw.extract_thumb()
        if thumb.format == rawpy.ThumbFormat.JPEG:
            return bytes(thumb.data)
    except Exception:
        # Unsupported/corrupt RAW falls through to the embedded-JPEG fallback.
        return None
    return None


def _preview_bytes(path: Path, extension: str, source_type: str) -> bytes | None:
    if source_type == "rendered" and extension in _JPEG_EXTENSIONS:
        try:
            return path.read_bytes()
        except OSError:
            return None

    if source_type == "raw":
        preview = _rawpy_preview(path)
        if preview is not None:
            return preview

    return extract_embedded_jpeg(path)


def _fit_preview(payload: bytes) -> bytes:
    try:
        import cv2
        import numpy as np

        encoded = np.frombuffer(payload, dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if image is None:
            return payload
        height, width = image.shape[:2]
        largest = max(height, width)
        if largest > _MAX_PREVIEW_EDGE:
            scale = _MAX_PREVIEW_EDGE / float(largest)
            image = cv2.resize(
                image,
                (max(1, round(width * scale)), max(1, round(height * scale))),
                interpolation=cv2.INTER_AREA,
            )
        ok, output = cv2.imencode(
            ".jpg",
            image,
            [int(cv2.IMWRITE_JPEG_QUALITY), 90],
        )
        if ok:
            return output.tobytes()
    except Exception:
        pass
    return payload


def _cache_path(fingerprint: str) -> Path:
    return (
        user_data_dir()
        / "preview_cache"
        / _CACHE_VERSION
        / fingerprint[:2]
        / f"{fingerprint}.jpg"
    )


def _cached_preview(fingerprint: str) -> bytes | None:
    path = _cache_path(fingerprint)
    try:
        if path.is_file():
            return path.read_bytes()
    except OSError:
        return None
    return None


def _write_cached_preview(fingerprint: str, payload: bytes) -> None:
    path = _cache_path(fingerprint)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".jpg.tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)
    except OSError:
        # Preview caching is an optimization, never a reason to fail review.
        return


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

    cached = _cached_preview(fingerprint)
    if cached is not None:
        return cached

    preview = _preview_bytes(path, match.extension, match.source_type)
    if preview is None:
        raise PreviewUnavailable("אין תצוגת מצלמה בקובץ הזה.")

    preview = _fit_preview(preview)
    _write_cached_preview(fingerprint, preview)
    return preview
