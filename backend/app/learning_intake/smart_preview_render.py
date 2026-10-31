"""Layer 2-3 of the bundled Smart Preview decoder: the "before" image.

Renders a decoded Smart Preview the way Lightroom shows the photo after Reset (Adobe Color, As Shot white
balance, default tone), i.e. the unedited starting point. The photographer's Develop settings are never read.
The author benchmarked this rendering against Lightroom's own Smart Preview exports (Delta E 2.51 on 80 held-out
Canon R6 II photos, 0.94-4.11 on 7 cameras); it has NOT been re-measured on this catalog, so it stays research-only
and never makes a sample training-ready.

Look: Adobe's "Adobe Color.xmp" look table, which ships with Lightroom / Camera Raw (Adobe's file, not bundled).
Looked up in this order: PROGRAPHER_ADOBE_COLOR_XMP, <data dir>/adobe_profiles/, then Adobe's settings and
Lightroom install folders (bounded, read-only walk). If it is not found, the look table embedded in the Smart
Preview's own profile is used instead (author's benchmark: 3.57% vs 3.48% pixel error, i.e. nearly the same).

Lens: when the Smart Preview's EXIF names a lens that has an Adobe RAW lens profile (.lcp, installed with Lightroom),
its light-falloff (vignetting) correction is applied, as Lightroom does with lens profile corrections on (the
common wedding setup, and the setup of the Canon R6 II benchmark). Distortion is not applied.
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
LENS_ROOT_PARTS = ("Adobe", "CameraRaw", "LensProfiles")
MAX_LENS_FILES = 100_000
THUMBNAIL_EDGE = 512
MISS_RETRY_SECONDS = 60  # one probe renders up to 4 samples: search the disk once, not four times
_found_look: dict[str, Any] = {}
_lens_files: dict[str, list[Path]] = {}


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


def lens_search_roots() -> list[Path]:
    if platform.system() == "Windows":
        return [Path(os.environ[e]).joinpath(*LENS_ROOT_PARTS) for e in ("PROGRAMDATA", "APPDATA") if os.getenv(e)]
    if platform.system() == "Darwin":
        return [Path("/Library/Application Support").joinpath(*LENS_ROOT_PARTS),
                (Path.home() / "Library" / "Application Support").joinpath(*LENS_ROOT_PARTS)]
    return []


def _norm(text: str | None) -> str:
    return "".join(ch for ch in (text or "").casefold() if ch.isalnum())


def _raw_lens_profiles() -> list[Path]:
    """Every Adobe RAW lens profile file (names only, listed once per process)."""
    if "files" not in _lens_files:
        files: list[Path] = []
        for root in lens_search_roots():
            if not root.is_dir():
                continue
            for folder, _dirs, names in os.walk(root, followlinks=False, onerror=lambda _e: None):
                files += [Path(folder) / n for n in names
                          if n.casefold().endswith(".lcp") and "raw" in n.casefold()]
                if len(files) > MAX_LENS_FILES:
                    break
        _lens_files["files"] = files
    return _lens_files["files"]


def lens_exif(path: Path) -> tuple[str, float, float] | None:
    """(lens model, focal length mm, f-number) from the Smart Preview's own EXIF, or None."""
    import tifffile

    def number(value) -> float | None:
        try:
            v = [float(x) for x in (value if isinstance(value, (tuple, list)) else [value])]
            return v[0] / v[1] if len(v) == 2 and v[1] else v[0]
        except (TypeError, ValueError, IndexError):
            return None

    try:
        with tifffile.TiffFile(str(path)) as tif:
            tag = tif.pages[0].tags.get(34665)
            exif = tag.value if tag is not None and isinstance(tag.value, dict) else {}
    except Exception:  # noqa: BLE001
        return None
    model = str(exif.get("LensModel") or "").strip()
    focal, fnum = number(exif.get("FocalLength")), number(exif.get("FNumber"))
    if not model or not focal or not fnum or focal <= 0 or fnum <= 0:
        return None
    return model, focal, fnum


def find_lens_entries(decoder, lens_model: str) -> list[dict] | None:
    """Vignetting entries of the Adobe RAW profile for this lens, or None. Adobe names the files
    '<camera> (<maker> <lens>) - RAW.lcp'; candidates are matched on the name, then confirmed on the Lens field."""
    import importlib

    want = _norm(lens_model)
    if len(want) < 4:
        return None
    lens_mod = importlib.import_module(decoder.__name__ + ".lens")
    for path in sorted((p for p in _raw_lens_profiles() if want in _norm(p.stem)), key=lambda p: len(p.stem)):
        try:
            name, entries = lens_mod.read_lcp(path)
        except Exception:  # noqa: BLE001
            continue
        if entries and _norm(name).endswith(want):
            return entries
    return None


def lens_vignetting_gain(decoder, path: Path, shape: tuple[int, int]):
    """(gain map or None, status) for the upright image shape."""
    import importlib

    exif = lens_exif(path)
    if exif is None:
        return None, "no_lens_metadata"
    entries = find_lens_entries(decoder, exif[0])
    if entries is None:
        return None, "lens_profile_not_found"
    h, w = shape
    small = (max(8, round(64 * h / max(h, w))), max(8, round(64 * w / max(h, w))))
    lens_mod = importlib.import_module(decoder.__name__ + ".lens")
    return lens_mod.vignette_gain(entries, exif[1], exif[2], small), "applied"


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


def render_reset_preview(decoder, sp, path: Path) -> dict[str, Any]:
    """Reset-look sRGB preview of an already decoded Smart Preview, as a small in-memory JPEG (never written to
    disk) plus its mean brightness. No path, file or lens name is returned."""
    import numpy as np
    from PIL import Image

    look = find_adobe_color_look(decoder)
    small = dataclasses.replace(sp, linear=_downscale(sp.linear, THUMBNAIL_EDGE))
    gain, lens_status = lens_vignetting_gain(decoder, path, small.linear.shape[:2])
    image = decoder.render_srgb(small, look=look, vignette_gain=gain)
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
        # "adobe_color_xmp" = the validated setup; "smart_preview_profile" = fallback when Lightroom's file is absent
        "look_source": "adobe_color_xmp" if look is not None else "smart_preview_profile",
        "lens_vignetting": lens_status,
        "thumbnail_jpeg_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
    }
