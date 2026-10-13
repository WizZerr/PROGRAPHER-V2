"""SP-01.04 — local neutral JPEG repeatability diagnostic, no Lightroom writes.

Two independently exported Smart Preview-only neutral JPEGs can be compared by
pixel content, dimensions and optional byte identity. This tool CANNOT prove
either export was reset, independent of master Develop, or sourced from the
same photo; those still need independently verified provenance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from app.photographer.smart_preview_analysis import (
    RESEARCH_ROOT_NAME,
    read_neutral_jpeg,
)

SCHEMA = "prographer.sp01.neutral_repeatability_research.v1"


def compare_decoded_jpegs(first: Path, second: Path) -> dict:
    """Pixel-level repeatability metrics, not an assessment of neutrality."""
    if first.resolve(strict=True) == second.resolve(strict=True):
        raise ValueError("independent candidate inputs must be separate files")
    a, hash_a = read_neutral_jpeg(first)
    b, hash_b = read_neutral_jpeg(second)
    size_match = a.size == b.size
    report = {
        "schema": SCHEMA,
        "source_kind": "TWO_USER_ATTESTED_SMART_PREVIEW_NEUTRAL_JPEG_EXPORTS",
        "dimensions_match": size_match,
        "first_dimensions": {"width": a.width, "height": a.height},
        "second_dimensions": {"width": b.width, "height": b.height},
        "byte_hashes_match": hash_a == hash_b,
        "pixel_equal": False,
        "mean_absolute_rgb_difference_8bit": None,
        "max_absolute_rgb_difference_8bit": None,
        "fraction_pixel_channels_exact_match": None,
        "fraction_pixels_all_channels_exact_match": None,
        "pixel_p95_absolute_rgb_difference_8bit": None,
        "candidate_repeatability_pass": False,
        "independent_export_provenance_verified": False,
        "neutrality_independent_of_master_develop_proven": False,
        "learning_eligibility": False,
    }
    if not size_match:
        return report
    left = np.asarray(a.convert("RGB"), dtype=np.int16)
    right = np.asarray(b.convert("RGB"), dtype=np.int16)
    diff = np.abs(left - right)
    report.update({
        "pixel_equal": bool(np.all(diff == 0)),
        "mean_absolute_rgb_difference_8bit": round(float(np.mean(diff)), 6),
        "max_absolute_rgb_difference_8bit": int(np.max(diff)),
        "fraction_pixel_channels_exact_match": round(float(np.mean(diff == 0)), 6),
        "fraction_pixels_all_channels_exact_match": round(
            float(np.mean(np.all(diff == 0, axis=2))), 6
        ),
        "pixel_p95_absolute_rgb_difference_8bit": round(
            float(np.percentile(diff, 95)), 6
        ),
        # Strict engineering policy for *identical* render/export settings.
        # Any different pixels trigger review rather than silent tolerance.
        "candidate_repeatability_pass": bool(np.all(diff == 0)),
    })
    return report


def _private_guard(first: Path, second: Path, output_dir: Path) -> tuple[Path, Path, Path]:
    root = (Path.home() / "Documents" / RESEARCH_ROOT_NAME).resolve(strict=True)
    if root.name != RESEARCH_ROOT_NAME or not root.is_dir():
        raise ValueError("invalid private research root")
    inputs = []
    for item in (first, second):
        if item.is_symlink():
            raise ValueError("symlink source denied")
        src = item.resolve(strict=True)
        if not src.is_file() or not src.is_relative_to(root):
            raise ValueError("input outside private research root")
        inputs.append(src)
    if inputs[0] == inputs[1]:
        raise ValueError("same input file")
    if output_dir.is_symlink():
        raise ValueError("symlink output denied")
    dest = output_dir.resolve()
    if not dest.is_relative_to(root) or dest == root:
        raise ValueError("output outside private research root")
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise ValueError("output exists and is not empty")
    if any(dest == x or dest.is_relative_to(x.parent) for x in inputs):
        raise ValueError("output cannot be under input folder")
    return inputs[0], inputs[1], dest


def run_research(first: Path, second: Path, output_dir: Path) -> dict:
    a, b, dest = _private_guard(first, second, output_dir)
    result = compare_decoded_jpegs(a, b)
    # No path, photo ID, original Develop, pixel array or private hash logged.
    dest.mkdir(parents=True, exist_ok=True)
    with (dest / "SP01_REPEATABILITY_AGGREGATE.json").open(
        "x", encoding="utf-8"
    ) as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
    return result


def main() -> int:
    cli = argparse.ArgumentParser(description="Compare two independently exported neutral research JPEGs")
    cli.add_argument("--first", type=Path, required=True)
    cli.add_argument("--second", type=Path, required=True)
    cli.add_argument("--out-dir", type=Path, required=True)
    cli.add_argument("--consent-acknowledged", action="store_true")
    cli.add_argument("--both-smart-preview-only-exports-confirmed", action="store_true")
    cli.add_argument("--same-reset-recipe-export-settings-confirmed", action="store_true")
    args = cli.parse_args()
    if not (
        args.consent_acknowledged
        and args.both_smart_preview_only_exports_confirmed
        and args.same_reset_recipe_export_settings_confirmed
    ):
        cli.error("local consent, offline originals and identical reset/export settings must be confirmed")
    try:
        result = run_research(args.first, args.second, args.out_dir)
    except (ValueError, OSError, RuntimeError, MemoryError) as exc:
        cli.exit(2, f"SP-01 REPEATABILITY STOPPED: {type(exc).__name__}\n")
    print("SP-01 pixel-identical render:", result["pixel_equal"])
    print("Dimensions match:", result["dimensions_match"])
    print("Repeatability candidate PASS:", result["candidate_repeatability_pass"])
    print("Neutrality independently proven: False; training ready: False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
