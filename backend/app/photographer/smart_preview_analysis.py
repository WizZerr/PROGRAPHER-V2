"""SP-01.01: private, source-only analysis of a neutral Smart Preview JPEG.

Research only. Lightroom must first create/verify the neutral JPEG in an
isolated copied catalog. This module NEVER opens a catalog, applies Develop,
modifies photos or reads the photographer's final recipe. It must not be
used as training input until the independent anti-leakage gate is passed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

SCHEMA = "prographer.sp01.neutral_jpeg_analysis.v1"
REPRESENTATION = "sp01-neutral-lightroom-smart-preview-srgb-jpeg-research-v1"
MAX_JPEG_BYTES = 64 * 1024 * 1024
MAX_PIXELS = 40_000_000
RESEARCH_ROOT_NAME = "ProGrapher_Research_Private"


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_neutral_jpeg(path: Path) -> tuple[Image.Image, str]:
    """Read a JPEG as display-referred sRGB (never as decoded RAW-linear data).

    Caller must separately affirm Lightroom's sRGB export settings.
    """
    if path.is_symlink() or not path.is_file() or path.suffix.lower() not in (".jpg", ".jpeg"):
        raise ValueError("expected a real neutral JPEG file")
    size = path.stat().st_size
    if not 1024 <= size <= MAX_JPEG_BYTES:
        raise ValueError("JPEG size outside research bounds")
    before = _digest(path)
    try:
        with Image.open(path) as source:
            if source.format != "JPEG":
                raise ValueError("input is not a JPEG")
            if source.width * source.height > MAX_PIXELS:
                raise ValueError("image pixel count outside research bounds")
            # An explicit embedded non-sRGB ICC must not be silently interpreted
            # as sRGB. No-ICC JPEGs require human sRGB export confirmation.
            if source.info.get("icc_profile"):
                from PIL import ImageCms
                profile = ImageCms.ImageCmsProfile(
                    __import__("io").BytesIO(source.info["icc_profile"])
                )
                label = ImageCms.getProfileDescription(profile).casefold()
                if "srgb" not in label and "s-rgb" not in label:
                    raise ValueError("embedded ICC is not sRGB")
            oriented = ImageOps.exif_transpose(source)
            image = oriented.convert("RGB").copy()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("JPEG cannot be decoded") from exc
    if before != _digest(path):
        raise ValueError("JPEG changed during analysis")
    return image, before


def srgb_visual_metrics(image: Image.Image) -> dict[str, float]:
    """Correctly linearize sRGB before measuring brightness (not sensor data)."""
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    if rgb.ndim != 3 or rgb.shape[2] != 3 or not rgb.size:
        raise ValueError("invalid display image")
    # A bounded deterministic sample avoids excessive memory on large photos.
    stride = max(1, int(np.ceil(np.sqrt((rgb.shape[0] * rgb.shape[1]) / 250_000))))
    rgb = rgb[::stride, ::stride, :] / 255.0
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    lum = (0.2126 * linear[:, :, 0] + 0.7152 * linear[:, :, 1]
           + 0.0722 * linear[:, :, 2]).reshape(-1)
    means = np.mean(rgb.reshape(-1, 3), axis=0)
    return {
        "linearized_srgb_luminance_p05": round(float(np.percentile(lum, 5)), 6),
        "linearized_srgb_luminance_p50": round(float(np.median(lum)), 6),
        "linearized_srgb_luminance_p95": round(float(np.percentile(lum, 95)), 6),
        "linearized_srgb_fraction_below_0_03": round(float(np.mean(lum < 0.03)), 6),
        "display_srgb_fraction_near_white": round(float(np.mean(np.any(rgb >= 0.985, axis=2))), 6),
        "display_srgb_mean_red": round(float(means[0]), 6),
        "display_srgb_mean_green": round(float(means[1]), 6),
        "display_srgb_mean_blue": round(float(means[2]), 6),
    }


def analyze_neutral_jpeg(
    path: Path, *, predictor: Any | None = None,
) -> dict[str, Any]:
    """Analyze ONLY the neutral JPEG; no Lightroom targets enter this function."""
    image, sha = read_neutral_jpeg(path)
    metrics = srgb_visual_metrics(image)
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "representation_version": REPRESENTATION,
        "source_kind": "USER_PREPARED_SMART_PREVIEW_NEUTRAL_JPEG_UNVERIFIED",
        "source_path_PRIVATE": str(path.resolve()),
        "source_sha256_PRIVATE": sha,
        "dimensions": {"width": image.width, "height": image.height},
        "metrics_display_referred_NOT_RAW": metrics,
        "scene": {
            "suggested_label": "UNKNOWN",
            "abstained": True,
            "status": "AI_NOT_RUN",
        },
        "photographer_develop_target_in_model_input": False,
        "independent_neutrality_leakage_gate_passed": False,
        "training_ready": False,
    }
    if predictor is not None:
        # The existing model is reused but may only see the NEUTRAL image.
        from app.photographer.raw_auto_scene_review import SCENE_CHOICES
        guess = predictor.predict(image)
        if not isinstance(guess, dict) or guess.get("suggested_label") not in dict(SCENE_CHOICES):
            raise ValueError("AI returned an invalid scene class")
        if guess["suggested_label"] != "UNKNOWN" and guess.get("abstained") is not False:
            raise ValueError("AI returned inconsistent abstention status")
        result["scene"] = {
            **guess,
            "status": "ZERO_SHOT_UNCALIBRATED_HUMAN_REVIEW_REQUIRED",
        }
    return result


def _private_paths(neutral_jpeg: Path, output_dir: Path) -> tuple[Path, Path]:
    """Prevent analysis outside the user's isolated Documents research root."""
    root = Path.home() / "Documents" / RESEARCH_ROOT_NAME
    root = root.resolve(strict=True)
    if root.name != RESEARCH_ROOT_NAME:
        raise ValueError("research root invalid")
    for p in (neutral_jpeg, output_dir):
        if p.is_symlink():
            raise ValueError("symlink paths are forbidden")
    src = neutral_jpeg.resolve(strict=True)
    dest = output_dir.resolve()
    if (not src.is_relative_to(root) or not dest.is_relative_to(root)
            or src.is_relative_to(dest) or dest == root
            or dest.is_relative_to(src.parent)):
        raise ValueError("input/output must be distinct private research paths")
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise ValueError("output directory must be new or empty")
    return src, dest


def run_research(
    neutral_jpeg: Path, output_dir: Path, *, predictor: Any | None = None,
) -> dict[str, Any]:
    src, dest = _private_paths(neutral_jpeg, output_dir)
    result = analyze_neutral_jpeg(src, predictor=predictor)
    aggregate = {
        "schema": SCHEMA,
        "representation_version": REPRESENTATION,
        "analyzed": 1,
        "scene_status": result["scene"]["status"],
        "unknown_or_abstained": bool(result["scene"].get("abstained")),
        "failed": 0,
        "training_ready": 0,
        "note": "Display-referred metrics; neutral/identity provenance and photographer targets NOT validated",
    }
    # Never overwrite any previous research artifacts.
    dest.mkdir(parents=True, exist_ok=True)
    with (dest / "SP01_ANALYSIS_PRIVATE.json").open("x", encoding="utf-8") as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
    with (dest / "SP01_AGGREGATE.json").open("x", encoding="utf-8") as out:
        json.dump(aggregate, out, ensure_ascii=False, indent=2)
    return aggregate


def main() -> int:
    cli = argparse.ArgumentParser(description="SP-01 private neutral Smart Preview JPEG analysis")
    cli.add_argument("--neutral-jpeg", required=True, type=Path)
    cli.add_argument("--out-dir", required=True, type=Path)
    cli.add_argument("--consent-acknowledged", action="store_true")
    cli.add_argument("--offline-smart-preview-confirmed", action="store_true")
    cli.add_argument("--neutral-reset-and-srgb-confirmed", action="store_true")
    cli.add_argument("--run-scene-ai", action="store_true")
    cli.add_argument("--allow-model-download", action="store_true")
    args = cli.parse_args()
    if not (args.consent_acknowledged and args.offline_smart_preview_confirmed
            and args.neutral_reset_and_srgb_confirmed):
        cli.error("private photographer permission, offline Smart Preview and reset/sRGB export must be confirmed")
    if args.allow_model_download and not args.run_scene_ai:
        cli.error("--allow-model-download requires --run-scene-ai")
    try:
        predictor = None
        if args.run_scene_ai:
            from app.photographer.raw_auto_scene_review import LocalClip
            predictor = LocalClip(allow_model_download=args.allow_model_download)
        aggregate = run_research(args.neutral_jpeg, args.out_dir, predictor=predictor)
    except (ValueError, OSError, RuntimeError, MemoryError) as exc:
        # No exception messages exposed: may contain private filesystem paths.
        cli.exit(2, "SP-01 STOPPED: " + type(exc).__name__ + " (private inputs unchanged)\n")
    print("SP-01 neutral JPEG analyzed; AI run:", args.run_scene_ai)
    print("Scene uncertain:", aggregate["unknown_or_abstained"])
    print("Training-ready: 0 (source/target anti-leak gate remains open)")
    print("PRIVATE output: keep analysis JSON and neutral JPEG on device")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
