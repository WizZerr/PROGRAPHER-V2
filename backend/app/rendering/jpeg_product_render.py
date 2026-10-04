from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import threading
from typing import Any

import cv2
import numpy as np

from app.catalog.event_store import EventStore
from app.datasets.jpeg_integrity import (
    JpegIntegrityError,
    read_jpeg_working_rgb,
    sha256_file,
)
from app.platform.paths import user_data_dir
from app.rendering.jpeg_renderer import (
    JPEG_RENDERER_CONTRACT_VERSION,
    build_polynomial_recipe,
    render_recipe_uint8,
    validate_jpeg_edit_recipe,
)
from app.services.event_service import EventOpenError, list_event_files


JPEG_PRODUCT_RENDER_CACHE_SCHEMA = "prographer.jpeg-product-render-cache.v1"
JPEG_PRODUCT_RENDER_CACHE_VERSION = "v1"
JPEG_PRODUCT_PREVIEW_MAX_EDGE = 1600


class JpegProductRenderError(ValueError):
    pass


class JpegRenderSourceUnavailable(JpegProductRenderError):
    pass


class JpegRenderRevisionConflict(JpegProductRenderError):
    pass


class JpegRenderStaleRevision(JpegProductRenderError):
    pass


@dataclass(frozen=True)
class JpegRenderArtifact:
    payload: bytes
    media_type: str
    mode: str
    revision: int
    recipe_sha256: str
    source_sha256: str
    width: int
    height: int
    cache_hit: bool


_LOCKS_GUARD = threading.Lock()
_RENDER_LOCKS: dict[str, threading.Lock] = {}


def _render_lock(event_id: str, fingerprint: str) -> threading.Lock:
    key = f"{event_id}:{fingerprint}"
    with _LOCKS_GUARD:
        lock = _RENDER_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _RENDER_LOCKS[key] = lock
        return lock


def _canonical_recipe(recipe: dict[str, Any]) -> tuple[dict[str, Any], str]:
    coefficients = validate_jpeg_edit_recipe(recipe)
    canonical = build_polynomial_recipe(coefficients)
    encoded = json.dumps(
        canonical,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return canonical, sha256(encoded).hexdigest()


def resolve_jpeg_product_source(event_id: str, fingerprint: str) -> Path:
    store = EventStore()
    try:
        event = store.get_event(event_id)
        files = list_event_files(event_id, store)
    except (KeyError, EventOpenError) as exc:
        raise JpegRenderSourceUnavailable("event not found") from exc

    match = next(
        (item for item in files if item.fingerprint == fingerprint),
        None,
    )
    if match is None:
        raise JpegRenderSourceUnavailable("file not found in event")

    extension = match.extension.casefold()
    if match.source_type != "rendered" or extension not in {".jpg", ".jpeg"}:
        raise JpegRenderSourceUnavailable(
            "product JPEG renderer accepts tracked JPEG sources only"
        )

    root = Path(event.root_path).resolve()
    path = Path(match.absolute_path).resolve()
    if not path.is_file() or not path.is_relative_to(root):
        raise JpegRenderSourceUnavailable(
            "source JPEG is unavailable inside the event root"
        )
    return path


def _cache_root(event_id: str, fingerprint: str) -> Path:
    event_key = sha256(event_id.encode("utf-8")).hexdigest()[:24]
    file_key = sha256(fingerprint.encode("utf-8")).hexdigest()
    return (
        user_data_dir()
        / "jpeg_product_render_cache"
        / JPEG_PRODUCT_RENDER_CACHE_VERSION
        / event_key
        / file_key[:2]
        / file_key
    )


def _revision_dir(event_id: str, fingerprint: str, revision: int) -> Path:
    return _cache_root(event_id, fingerprint) / f"r{revision:08d}"


def _latest_path(event_id: str, fingerprint: str) -> Path:
    return _cache_root(event_id, fingerprint) / "latest.json"


def _manifest_path(event_id: str, fingerprint: str, revision: int) -> Path:
    return _revision_dir(event_id, fingerprint, revision) / "manifest.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else None
    except (OSError, ValueError):
        return None
    return None


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _encode_png(rgb: np.ndarray) -> bytes:
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    ok, encoded = cv2.imencode(
        ".png",
        bgr,
        [int(cv2.IMWRITE_PNG_COMPRESSION), 3],
    )
    if not ok:
        raise JpegProductRenderError("failed to encode transient render")
    return encoded.tobytes()


def _preview_source(rgb: np.ndarray) -> np.ndarray:
    height, width = rgb.shape[:2]
    largest = max(height, width)
    if largest <= JPEG_PRODUCT_PREVIEW_MAX_EDGE:
        return rgb

    scale = JPEG_PRODUCT_PREVIEW_MAX_EDGE / float(largest)
    target = (
        max(1, round(width * scale)),
        max(1, round(height * scale)),
    )
    return cv2.resize(rgb, target, interpolation=cv2.INTER_AREA)


def _validate_revision(revision: int) -> int:
    if isinstance(revision, bool) or int(revision) != revision or revision < 1:
        raise JpegProductRenderError("revision must be an integer >= 1")
    return int(revision)


def _check_latest(
    latest: dict[str, Any] | None,
    *,
    revision: int,
    recipe_sha256: str,
    source_sha256: str,
) -> None:
    if not latest:
        return

    current_revision = int(latest.get("revision") or 0)
    if revision < current_revision:
        raise JpegRenderStaleRevision(
            f"revision {revision} is stale; current revision is {current_revision}"
        )

    if revision == current_revision:
        if latest.get("recipe_sha256") != recipe_sha256:
            raise JpegRenderRevisionConflict(
                "revision already belongs to a different JPEG EditRecipe"
            )
        if latest.get("source_sha256") != source_sha256:
            raise JpegRenderRevisionConflict(
                "source bytes changed for the current render revision"
            )


def _load_cached_artifact(
    *,
    event_id: str,
    fingerprint: str,
    revision: int,
    mode: str,
    recipe_sha256: str,
    source_sha256: str,
) -> JpegRenderArtifact | None:
    manifest = _read_json(_manifest_path(event_id, fingerprint, revision))
    if not manifest:
        return None

    if manifest.get("schema") != JPEG_PRODUCT_RENDER_CACHE_SCHEMA:
        return None
    if manifest.get("recipe_sha256") != recipe_sha256:
        raise JpegRenderRevisionConflict(
            "cached revision belongs to a different JPEG EditRecipe"
        )
    if manifest.get("source_sha256") != source_sha256:
        raise JpegRenderRevisionConflict(
            "source bytes changed for an existing cached revision"
        )

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    entry = artifacts.get(mode)
    if not isinstance(entry, dict):
        return None

    filename = entry.get("file")
    if not isinstance(filename, str) or not filename:
        return None
    artifact_path = _revision_dir(event_id, fingerprint, revision) / filename
    try:
        payload = artifact_path.read_bytes()
    except OSError:
        return None

    return JpegRenderArtifact(
        payload=payload,
        media_type="image/png",
        mode=mode,
        revision=revision,
        recipe_sha256=recipe_sha256,
        source_sha256=source_sha256,
        width=int(entry["width"]),
        height=int(entry["height"]),
        cache_hit=True,
    )


def _write_artifact(
    *,
    event_id: str,
    fingerprint: str,
    revision: int,
    mode: str,
    recipe_sha256: str,
    source_sha256: str,
    payload: bytes,
    width: int,
    height: int,
) -> None:
    revision_dir = _revision_dir(event_id, fingerprint, revision)
    filename = f"{mode}.png"
    _atomic_write_bytes(revision_dir / filename, payload)

    manifest_path = _manifest_path(event_id, fingerprint, revision)
    manifest = _read_json(manifest_path) or {
        "schema": JPEG_PRODUCT_RENDER_CACHE_SCHEMA,
        "renderer_contract_version": JPEG_RENDERER_CONTRACT_VERSION,
        "event_id": event_id,
        "fingerprint": fingerprint,
        "revision": revision,
        "recipe_sha256": recipe_sha256,
        "source_sha256": source_sha256,
        "preview_max_edge": JPEG_PRODUCT_PREVIEW_MAX_EDGE,
        "artifacts": {},
    }
    manifest["artifacts"][mode] = {
        "file": filename,
        "width": width,
        "height": height,
    }
    _atomic_write_json(manifest_path, manifest)


def _write_latest(
    *,
    event_id: str,
    fingerprint: str,
    revision: int,
    recipe_sha256: str,
    source_sha256: str,
) -> None:
    _atomic_write_json(
        _latest_path(event_id, fingerprint),
        {
            "schema": JPEG_PRODUCT_RENDER_CACHE_SCHEMA,
            "revision": revision,
            "recipe_sha256": recipe_sha256,
            "source_sha256": source_sha256,
            "renderer_contract_version": JPEG_RENDERER_CONTRACT_VERSION,
        },
    )


def render_jpeg_product(
    *,
    event_id: str,
    fingerprint: str,
    recipe: dict[str, Any],
    revision: int,
    mode: str,
) -> JpegRenderArtifact:
    revision = _validate_revision(revision)
    if mode not in {"preview", "full"}:
        raise JpegProductRenderError("mode must be 'preview' or 'full'")

    canonical_recipe, recipe_sha256 = _canonical_recipe(recipe)
    source_path = resolve_jpeg_product_source(event_id, fingerprint)
    source_sha256 = sha256_file(source_path)

    lock = _render_lock(event_id, fingerprint)
    with lock:
        latest = _read_json(_latest_path(event_id, fingerprint))
        _check_latest(
            latest,
            revision=revision,
            recipe_sha256=recipe_sha256,
            source_sha256=source_sha256,
        )

        cached = _load_cached_artifact(
            event_id=event_id,
            fingerprint=fingerprint,
            revision=revision,
            mode=mode,
            recipe_sha256=recipe_sha256,
            source_sha256=source_sha256,
        )
        if cached is not None:
            if not latest or revision > int(latest.get("revision") or 0):
                _write_latest(
                    event_id=event_id,
                    fingerprint=fingerprint,
                    revision=revision,
                    recipe_sha256=recipe_sha256,
                    source_sha256=source_sha256,
                )
            return cached

        try:
            source_rgb, _ = read_jpeg_working_rgb(source_path)
        except (JpegIntegrityError, OSError) as exc:
            raise JpegProductRenderError(
                f"JPEG working-space decode failed: {source_path.name}"
            ) from exc

        render_source = (
            _preview_source(source_rgb)
            if mode == "preview"
            else source_rgb
        )
        rendered = render_recipe_uint8(render_source, canonical_recipe)
        payload = _encode_png(rendered)
        height, width = rendered.shape[:2]

        _write_artifact(
            event_id=event_id,
            fingerprint=fingerprint,
            revision=revision,
            mode=mode,
            recipe_sha256=recipe_sha256,
            source_sha256=source_sha256,
            payload=payload,
            width=int(width),
            height=int(height),
        )
        _write_latest(
            event_id=event_id,
            fingerprint=fingerprint,
            revision=revision,
            recipe_sha256=recipe_sha256,
            source_sha256=source_sha256,
        )

        return JpegRenderArtifact(
            payload=payload,
            media_type="image/png",
            mode=mode,
            revision=revision,
            recipe_sha256=recipe_sha256,
            source_sha256=source_sha256,
            width=int(width),
            height=int(height),
            cache_hit=False,
        )


def assert_current_jpeg_revision(
    *,
    event_id: str,
    fingerprint: str,
    recipe: dict[str, Any],
    revision: int,
) -> str:
    revision = _validate_revision(revision)
    _, recipe_sha256 = _canonical_recipe(recipe)
    source_path = resolve_jpeg_product_source(event_id, fingerprint)
    source_sha256 = sha256_file(source_path)

    lock = _render_lock(event_id, fingerprint)
    with lock:
        latest = _read_json(_latest_path(event_id, fingerprint))
        if not latest:
            raise JpegRenderStaleRevision(
                "no current rendered revision exists for this JPEG"
            )
        _check_latest(
            latest,
            revision=revision,
            recipe_sha256=recipe_sha256,
            source_sha256=source_sha256,
        )
        current_revision = int(latest.get("revision") or 0)
        if revision != current_revision:
            raise JpegRenderStaleRevision(
                f"revision {revision} is not current; current revision is {current_revision}"
            )
        return recipe_sha256
