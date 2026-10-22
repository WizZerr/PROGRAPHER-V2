"""PG-LI-02B.01 — bounded, read-only Smart Preview DNG inspection.

This is a CONTENT/DECODE capability check, not a photo-identity join and
never an approved source-only model feature. Smart Previews can differ from
the untouched original; Lightroom/SDK verification is a separate gate.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import os
from typing import Any

from app.learning_intake.service import LearningIntakeError

MAX_ENTRIES = 100_000
MAX_DECODE = 4
MAX_DNG_BYTES = 120 * 1024 * 1024
MAX_PIXEL_DIMENSION = 12_000
TIFF_SIGNATURES = (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")


def _count_dng_files(root: Path) -> tuple[dict[str, int], list[Path]]:
    counts: Counter[str] = Counter()
    dng: list[Path] = []
    visited = 0

    def walk_error(_error: OSError) -> None:
        raise LearningIntakeError("Unable to inspect all Smart Preview subfolders.")

    for folder, subdirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        base = Path(folder)
        subdirs[:] = sorted(
            d for d in subdirs
            if not (base / d).is_symlink() and not (base / d).is_junction()
        )
        for filename in sorted(files):
            file = base / filename
            if file.is_symlink():
                counts["symlink_entries_ignored"] += 1
                continue
            visited += 1
            if visited > MAX_ENTRIES:
                raise LearningIntakeError(
                    "Smart Previews folder is too large for this bounded pilot."
                )
            if file.suffix.casefold() != ".dng":
                counts["other_files"] += 1
                continue
            try:
                stat = file.stat()
                if stat.st_size == 0 or stat.st_size > MAX_DNG_BYTES:
                    counts["dng_size_excluded"] += 1
                    continue
                with file.open("rb") as stream:
                    header = stream.read(4)
                if header not in TIFF_SIGNATURES:
                    counts["invalid_dng_container_signature"] += 1
                    continue
            except OSError:
                counts["unreadable_dng"] += 1
                continue
            counts["dng_tiff_signature_candidates"] += 1
            dng.append(file)
    counts["visited_file_entries"] = visited
    return dict(sorted(counts.items())), dng


def _decode_sample(path: Path) -> dict[str, Any]:
    """Try to decode actual DNG pixel data with LibRaw; no image retained."""
    try:
        import rawpy
        import numpy as np
    except ImportError:
        return {"state": "decoder_unavailable"}

    try:
        original_stat = path.stat()
        # LibRaw may not support the particular lossy-DNG compression used by
        # this Lightroom version. Never silently substitute a JPEG preview.
        with rawpy.imread(str(path)) as img:
            raw_w = int(img.sizes.width)
            raw_h = int(img.sizes.height)
            if (
                raw_w <= 0 or raw_h <= 0
                or raw_w > MAX_PIXEL_DIMENSION or raw_h > MAX_PIXEL_DIMENSION
                or raw_w * raw_h > 35_000_000
            ):
                return {"state": "unsafe_dimensions"}
            pixels = img.postprocess(
                use_camera_wb=True, no_auto_bright=True,
                output_bps=8, half_size=True,
            )
            if getattr(pixels, "ndim", 0) != 3 or pixels.shape[2] != 3:
                return {"state": "unsupported_pixel_layout"}
            # Take spatially sparse pixels. This is only proof of decoding,
            # not valid color/scene features or Adobe neutral parity.
            sparse = np.asarray(pixels)[::32, ::32, :]
            if not np.isfinite(sparse).all():
                return {"state": "invalid_pixels"}
            values = sparse.astype("float32") / 255.0
            summary = {
                "state": "decoded_unverified",
                "width": int(pixels.shape[1]),
                "height": int(pixels.shape[0]),
                "preview_mean_luma": round(float(
                    np.mean(0.2126 * values[:, :, 0]
                            + 0.7152 * values[:, :, 1]
                            + 0.0722 * values[:, :, 2])
                ), 4),
            }
        updated_stat = path.stat()
        if (original_stat.st_size, original_stat.st_mtime_ns) != (
            updated_stat.st_size, updated_stat.st_mtime_ns
        ):
            return {"state": "changed_during_decode"}
        return summary
    except Exception:
        # The local engine must not expose arbitrary LibRaw exception paths
        # that could contain private folder/photographer names.
        return {"state": "unsupported_or_corrupt_dng"}


def inspect_smart_previews(root: Path, *, decode_limit: int = MAX_DECODE) -> dict[str, Any]:
    if not 0 <= decode_limit <= MAX_DECODE:
        raise LearningIntakeError("Smart Preview decode sample must be at most 4.")
    if root.is_symlink() or root.name.casefold().endswith(" smart previews.lrdata") is False:
        raise LearningIntakeError("Expected a direct Lightroom Smart Previews.lrdata folder.")
    try:
        resolved = root.resolve(strict=True)
    except OSError as exc:
        raise LearningIntakeError("Smart Previews folder is unavailable.") from exc
    if not resolved.is_dir():
        raise LearningIntakeError("Smart Previews path is not a directory.")

    counts, candidates = _count_dng_files(resolved)
    # Evenly-spaced pilot rather than all thumbnails at the beginning of
    # the catalog. No filenames/paths returned to the aggregate caller.
    sample: list[dict[str, Any]] = []
    if candidates and decode_limit:
        target = min(decode_limit, len(candidates))
        positions = [i * len(candidates) // target for i in range(target)]
        sample = [_decode_sample(candidates[p]) for p in positions]
    outcomes = Counter(entry["state"] for entry in sample)
    return {
        "schema": "prographer.learning_intake.smart_preview_probe.v1",
        "status": "DNG_CONTENT_PILOT_ONLY",
        "source_kind": "smart_previews",
        "counts": counts,
        "decode_attempts": len(sample),
        "decode_status_counts": dict(sorted(outcomes.items())),
        "decoded_samples": [entry for entry in sample if entry["state"] == "decoded_unverified"],
        "catalog_photo_identity_verified": False,
        "photo_to_dng_link_verified": False,
        "source_only_neutral_parity_verified": False,
        "photographer_finality_verified": False,
        "training_ready_samples": 0,
        "warnings": [
            "Actual DNG signatures and decode status are checked, but DNG-to-Lightroom photo identity is NOT verified.",
            "A decoded Smart Preview is NOT a validated representation of the pre-edit RAW as seen by the photographer.",
            "This inspection does not apply Develop, read/write catalogs or store decoded images.",
            "The Lightroom SDK smartPreviewInfo.smartPreviewPath readback is required for a trusted per-photo link.",
        ],
    }
