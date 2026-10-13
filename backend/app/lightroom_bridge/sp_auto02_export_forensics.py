"""SP-AUTO-02: inspect encoding and residuals of two verified, private JPEGs.

No Lightroom jobs or changes. Never expose EXIF field values, paths, hashes,
image pixels or the photographer's Develop target in the aggregate report.
Neither coding-table equality nor a tiny residual proves source independence.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, JpegImagePlugin

from app.lightroom_bridge import sp_auto01
from app.lightroom_bridge.sp_auto01_reference_compare import MANUAL_RELATIVE
from app.photographer.smart_preview_analysis import read_neutral_jpeg

SCHEMA = "prographer.spauto02.jpeg_render_forensics.v1"
DIRNAME = "SP01_JPEG_ENCODING_FORENSICS"
REPORT = "ENCODING_FORENSICS_AGGREGATE.json"


def _metadata(path: Path) -> dict:
    """Only non-identifying JPEG encoder/metadata structural diagnostics."""
    with Image.open(path) as im:
        if im.format != "JPEG":
            raise ValueError("not JPEG")
        qtables = im.quantization
        if not isinstance(qtables, dict):
            raise ValueError("JPEG quantization metadata unavailable")
        return {
            "quantization_tables": tuple(
                (int(index), tuple(int(x) for x in values))
                for index, values in sorted(qtables.items())
            ),
            "subsampling": JpegImagePlugin.get_sampling(im),
            "progressive": bool(im.info.get("progressive") or im.info.get("progression")),
            "icc": im.info.get("icc_profile", b""),
            "exif_present": bool(im.info.get("exif", b"")),
            "size_bytes": path.stat().st_size,
        }


def diagnostics(auto: Path, manual: Path) -> dict:
    """Compare decoded pixels, not original RAW sensor data."""
    if auto.resolve(strict=True) == manual.resolve(strict=True):
        raise ValueError("both references resolve to the same file")
    first, _ = read_neutral_jpeg(auto)
    second, _ = read_neutral_jpeg(manual)
    if first.size != second.size:
        return {
            "schema": SCHEMA, "dimensions_match": False,
            "diagnostic_status": "DIMENSION_MISMATCH_STOP",
            "no_leakage_proven": False, "training_ready": False,
        }

    a, b = _metadata(auto), _metadata(manual)
    first_rgb = np.asarray(first, dtype=np.int16)
    second_rgb = np.asarray(second, dtype=np.int16)
    delta = first_rgb - second_rgb
    error = np.abs(delta)
    signed_means = np.mean(delta, axis=(0, 1))
    mse = float(np.mean(delta.astype(np.float64) ** 2))
    # A small downsampled/blurred discrepancy can be consistent with encoder
    # differences, but is NOT a test that guarantees identical Develop settings.
    blur_a = np.asarray(first.filter(ImageFilter.BoxBlur(4)), dtype=np.int16)
    blur_b = np.asarray(second.filter(ImageFilter.BoxBlur(4)), dtype=np.int16)
    blur_error = np.abs(blur_a - blur_b)
    quant_equal = a["quantization_tables"] == b["quantization_tables"]
    sampling_equal = a["subsampling"] == b["subsampling"]
    icc_equal = a["icc"] == b["icc"]
    return {
        "schema": SCHEMA,
        "diagnostic_status": "COMPLETED_CAUSE_NOT_PROVEN",
        "dimensions_match": True,
        "decoded_rgb_pixel_equal": bool(np.all(error == 0)),
        "jpeg_quantization_tables_match": quant_equal,
        "jpeg_chroma_subsampling_match": sampling_equal,
        "jpeg_progressive_mode_match": a["progressive"] == b["progressive"],
        "jpeg_embedded_icc_bytes_match": icc_equal,
        "jpeg_exif_presence_match": a["exif_present"] == b["exif_present"],
        "auto_size_bytes": a["size_bytes"],
        "manual_size_bytes": b["size_bytes"],
        "mean_absolute_rgb_difference_8bit": round(float(np.mean(error)), 6),
        "max_absolute_rgb_difference_8bit": int(np.max(error)),
        "p99_absolute_channel_difference_8bit": round(
            float(np.percentile(error, 99)), 6
        ),
        "fraction_channels_exact": round(float(np.mean(error == 0)), 6),
        "fraction_channels_within_1": round(float(np.mean(error <= 1)), 6),
        "fraction_channels_within_2": round(float(np.mean(error <= 2)), 6),
        "signed_auto_minus_manual_RGB_means_8bit": {
            "red": round(float(signed_means[0]), 6),
            "green": round(float(signed_means[1]), 6),
            "blue": round(float(signed_means[2]), 6),
        },
        "rgb_psnr_db": round(10 * math.log10(255.0 ** 2 / mse), 4)
            if mse > 0 else None,
        "boxblur_radius_4_mean_abs_difference_8bit": round(
            float(np.mean(blur_error)), 6
        ),
        "encoding_difference_supported": not (
            quant_equal and sampling_equal and a["progressive"] == b["progressive"]
            and icc_equal
        ),
        "cause_of_pixel_difference_proven": False,
        "neutrality_independent_of_master_develop_proven": False,
        "training_ready": False,
    }


def run(*, root_override: Path | None = None) -> dict:
    verified, _ = sp_auto01.verify(root_override=root_override)
    if not verified:
        raise ValueError("previous Lightroom research job not verified")
    root, _, _, work = sp_auto01._context(root_override)
    state = sp_auto01._fields(work / "result.txt")
    auto = Path(state["jpeg"])
    manual = root / MANUAL_RELATIVE
    if manual.is_symlink() or not manual.is_file() or not manual.resolve(strict=True).is_relative_to(root):
        raise ValueError("private manual neutral reference missing or redirected")
    if any(part.is_symlink() for part in manual.parents if part != root and part.is_relative_to(root)):
        raise ValueError("manual reference parent is redirected")
    dest = work / DIRNAME
    if dest.is_symlink() or dest.exists():
        raise FileExistsError("forensic result already exists; never overwrite")
    metrics = diagnostics(auto, manual)
    dest.mkdir()
    with (dest / REPORT).open("x", encoding="utf-8") as fh:
        json.dump(metrics, fh, ensure_ascii=False, indent=2, allow_nan=False)
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Private JPEG export-encoding diagnostic; read-only")
    parser.add_argument("--research-consent", action="store_true")
    parser.add_argument("--same-photo-manual-reference-confirmed", action="store_true")
    args = parser.parse_args()
    if not (args.research_consent and args.same_photo_manual_reference_confirmed):
        parser.error("local research permission and verified same-photo manual reference required")
    try:
        d = run()
    except (OSError, ValueError, FileExistsError, MemoryError) as exc:
        parser.exit(2, f"SP-AUTO-02 FORENSICS STOPPED: {type(exc).__name__}\n")
    print("SP-AUTO-02 JPEG comparison metadata: COMPLETE")
    print("Quantization tables match:", d.get("jpeg_quantization_tables_match"))
    print("Chroma sampling match:", d.get("jpeg_chroma_subsampling_match"))
    print("Cause proven: False; training-ready: False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
