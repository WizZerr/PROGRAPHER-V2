"""Layer 2-3 of the bundled Smart Preview decoder: the "before" image.

Renders a decoded Smart Preview the way Lightroom shows the photo after Reset (Adobe Color, As Shot white
balance, default tone), i.e. the unedited starting point. The photographer's Develop settings are never read.
The author benchmarked this rendering against Lightroom's own Smart Preview exports (Delta E 2.51 on 80 held-out
Canon R6 II photos, 0.94-4.11 on 7 cameras); it has NOT been re-measured on this catalog, so it stays research-only
and never makes a sample training-ready.

Needs Adobe's "Adobe Color.xmp" look table, which ships with Lightroom / Camera Raw (Adobe's file, not bundled).
Looked up in this order: PROGRAPHER_ADOBE_COLOR_XMP, <data dir>/adobe_profiles/, then Adobe's settings and
Lightroom install folders (bounded, read-only walk).
Lens vignetting correction is not applied: Lightroom's default lens profile darkens corners less than this preview.
"""
from __future__ import annotations

import base64
import dataclasses
import io
import os
import platform
import time
from pathlib import Path
from typing import Any

from app.platform.paths import user_data_dir

LOOK_ENV = "PROGRAPHER_ADOBE_COLOR_XMP"
LOOK_FILENAME = "adobe color.xmp"
DROP_FOLDER = "adobe_profiles"
MAX_SEARCH_ENTRIES = 50_000
MAX_LOOK_BYTES = 2 * 1024 * 1024
THUMBNAIL_EDGE = 512
MISS_RETRY_SECONDS = 60  # one probe renders up to 4 samples: search the disk once, not four times
_found_look: dict[str, Any] = {}


def look_search_roots() -> list[Path]:
    roots: list[Path] = [user_data_dir() / DROP_FOLDER]
    if platform.system() == "Windows":
        for env, sub in (("PROGRAMDATA", r"Adobe\CameraRaw\Settings"), ("APPDATA", r"Adobe\CameraRaw\Settings"),
                         ("PROGRAMFILES", r"Adobe\Adobe Lightroom Classic")):
            if os.getenv(env):
                roots.append(Path(os.environ[env]) / sub)
    elif platform.system() == "Darwin":
        roots += [Path("/Library/Application Support/Adobe/CameraRaw/Settings"),
                  Path.home() / "Library" / "Application Support" / "Adobe" / "CameraRaw" / "Settings",
                  Path("/Applications/Adobe Lightroom Classic")]
    return roots


def _candidates() -> list[Path]:
    override = os.getenv(LOOK_ENV)
    if override:
        return [Path(override).expanduser()]
    found: list[Path] = []
    visited = 0
    for root in look_search_roots():
        if not root.is_dir():
            continue
        for folder, subdirs, files in os.walk(root, followlinks=False, onerror=lambda _e: None):
            visited += len(files) + len(subdirs)
            if visited > MAX_SEARCH_ENTRIES:
                break
            found += [Path(folder) / f for f in files if f.casefold() == LOOK_FILENAME]
        if visited > MAX_SEARCH_ENTRIES:
            break
    # Adobe keeps the raw-file profiles under "Adobe Raw"; prefer those over any other copy.
    return sorted(found, key=lambda p: "adobe raw" not in str(p).casefold())


def find_adobe_color_look(decoder) -> tuple | None:
    """(dims, table) of the first readable Adobe Color look table, or None. A success is cached; a miss only for
    a minute, so a file copied in later is picked up on a later probe without restarting."""
    explicit = bool(os.getenv(LOOK_ENV))  # an explicit file is always re-read, never cached
    if not explicit and "look" in _found_look:
        return _found_look["look"]
    if not explicit and time.monotonic() - _found_look.get("miss_at", -MISS_RETRY_SECONDS) < MISS_RETRY_SECONDS:
        return None
    for path in _candidates():
        try:
            if not path.is_file() or path.stat().st_size > MAX_LOOK_BYTES:
                continue
            look = decoder.read_look_table(path)
        except Exception:  # noqa: BLE001  (unreadable or not a look table: try the next one)
            continue
        if not explicit:
            _found_look["look"] = look
        return look
    if not explicit:
        _found_look["miss_at"] = time.monotonic()
    return None


def _downscale(linear, edge: int):
    import numpy as np
    from PIL import Image

    h, w = linear.shape[:2]
    scale = edge / max(h, w)
    if scale >= 1:
        return linear
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    return np.stack([np.asarray(Image.fromarray(np.ascontiguousarray(linear[..., c], dtype=np.float32))
                                .resize(size, Image.BILINEAR)) for c in range(3)], axis=-1)


def render_reset_preview(decoder, sp, look) -> dict[str, Any]:
    """Reset-look sRGB preview of an already decoded Smart Preview, as a small in-memory JPEG (never written to
    disk) plus its mean brightness. No path or file name is returned."""
    import numpy as np
    from PIL import Image

    small = dataclasses.replace(sp, linear=_downscale(sp.linear, THUMBNAIL_EDGE))
    image = decoder.render_srgb(small, look=look)
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
        return {"state": "reset_render_invalid_output"}
    lin = np.where(image / 255.0 <= 0.04045, image / 255.0 / 12.92, ((image / 255.0 + 0.055) / 1.055) ** 2.4)
    buffer = io.BytesIO()
    Image.fromarray(image).save(buffer, format="JPEG", quality=85)
    return {
        "state": "reset_rendered_unverified",
        "width": int(image.shape[1]),
        "height": int(image.shape[0]),
        "mean_srgb_luma": round(float(np.mean(lin @ np.array([0.2126, 0.7152, 0.0722]))), 4),
        "calibration_stops": float(getattr(decoder, "CALIBRATION_STOPS", 0.0)),
        "lens_vignetting_applied": False,
        "thumbnail_jpeg_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
    }
