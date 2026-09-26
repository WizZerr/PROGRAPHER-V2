from __future__ import annotations

from pathlib import Path

from app.catalog.event_store import EventStore
from app.platform.paths import user_data_dir
from app.services.event_service import EventOpenError, list_event_files


class PreviewUnavailable(ValueError):
    pass


_READ_LIMIT = 128 * 1024 * 1024
_MIN_JPEG_BYTES = 800
_JPEG_EXTENSIONS = {".jpg", ".jpeg"}
_CACHE_VERSION = "v3"
_MAX_PREVIEW_EDGE = 2400
_MIN_ACCEPTABLE_RAW_EDGE = 1400
_JPEG_QUALITY = 94


def _decode_jpeg(payload: bytes):
    try:
        import cv2
        import numpy as np

        encoded = np.frombuffer(payload, dtype=np.uint8)
        return cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _pixel_area(payload: bytes) -> int:
    image = _decode_jpeg(payload)
    if image is None:
        return 0
    height, width = image.shape[:2]
    return int(height) * int(width)


def extract_embedded_jpeg(path: Path) -> bytes | None:
    """
    Return the largest decodable JPEG preview embedded in a camera RAW.

    Some RAW/DNG files contain multiple JPEGs (tiny thumbnails plus a larger
    preview). Selection is based on decoded pixel area instead of byte size so
    the UI does not accidentally upscale a small thumbnail.
    """
    with path.open("rb") as handle:
        blob = handle.read(_READ_LIMIT)

    best: bytes | None = None
    best_area = 0
    start = 0

    while True:
        marker = blob.find(b"\xff\xd8\xff", start)
        if marker < 0:
            break

        end = blob.find(b"\xff\xd9", marker + 3)
        if end < 0:
            break

        chunk = blob[marker : end + 2]
        if len(chunk) >= _MIN_JPEG_BYTES:
            area = _pixel_area(chunk)
            if area > best_area or (
                area == best_area
                and area > 0
                and (best is None or len(chunk) > len(best))
            ):
                best = chunk
                best_area = area

        start = marker + 2

    return best


def _rawpy_thumbnail(path: Path) -> bytes | None:
    try:
        import rawpy
    except ImportError:
        return None

    try:
        with rawpy.imread(str(path)) as raw:
            thumb = raw.extract_thumb()
        if thumb.format == rawpy.ThumbFormat.JPEG:
            payload = bytes(thumb.data)
            return payload if _pixel_area(payload) > 0 else None
    except Exception:
        return None

    return None


def _rawpy_render(path: Path) -> bytes | None:
    """
    Render a high-quality review preview when embedded camera previews are too
    small or unavailable. This is cached, so the expensive path is paid once.
    """
    try:
        import cv2
        import rawpy
    except ImportError:
        return None

    try:
        with rawpy.imread(str(path)) as raw:
            rgb = raw.postprocess(
                half_size=True,
                use_camera_wb=True,
                no_auto_bright=False,
                output_bps=8,
            )

        # rawpy returns RGB; OpenCV JPEG encoding expects BGR.
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        ok, output = cv2.imencode(
            ".jpg",
            bgr,
            [int(cv2.IMWRITE_JPEG_QUALITY), _JPEG_QUALITY],
        )
        if ok:
            return output.tobytes()
    except Exception:
        return None

    return None


def _best_raw_preview(path: Path) -> bytes | None:
    candidates = [
        payload
        for payload in (
            _rawpy_thumbnail(path),
            extract_embedded_jpeg(path),
        )
        if payload is not None
    ]

    best = max(candidates, key=_pixel_area, default=None)
    best_image = _decode_jpeg(best) if best is not None else None
    best_edge = (
        max(best_image.shape[:2])
        if best_image is not None
        else 0
    )

    if best_edge < _MIN_ACCEPTABLE_RAW_EDGE:
        rendered = _rawpy_render(path)
        if rendered is not None and _pixel_area(rendered) > _pixel_area(best or b""):
            best = rendered

    return best


def _preview_bytes(path: Path, extension: str, source_type: str) -> bytes | None:
    if source_type == "rendered" and extension in _JPEG_EXTENSIONS:
        try:
            payload = path.read_bytes()
            return payload if _pixel_area(payload) > 0 else None
        except OSError:
            return None

    if source_type == "raw":
        return _best_raw_preview(path)

    return extract_embedded_jpeg(path)


def _fit_preview(payload: bytes) -> bytes | None:
    try:
        import cv2

        image = _decode_jpeg(payload)
        if image is None:
            return None

        height, width = image.shape[:2]
        largest = max(height, width)

        # Keep an already suitable JPEG byte-for-byte. Re-encoding small
        # previews only loses quality.
        if largest <= _MAX_PREVIEW_EDGE:
            return payload

        scale = _MAX_PREVIEW_EDGE / float(largest)
        image = cv2.resize(
            image,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
        ok, output = cv2.imencode(
            ".jpg",
            image,
            [int(cv2.IMWRITE_JPEG_QUALITY), _JPEG_QUALITY],
        )
        if ok:
            return output.tobytes()
    except Exception:
        return None

    return None


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
        raise PreviewUnavailable("אין תצוגת מצלמה תקינה בקובץ הזה.")

    preview = _fit_preview(preview)
    if preview is None:
        raise PreviewUnavailable("תצוגת המצלמה בקובץ אינה JPEG תקין.")

    _write_cached_preview(fingerprint, preview)
    return preview
