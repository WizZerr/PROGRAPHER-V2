"""SP-AUTO-01 — read-only reference comparison for the VERIFIED auto JPEG.

Uses the already-existing manual Lightroom reset/Smart Preview-only JPEG solely
as an engineering reference. The two workflows MAY differ in export settings,
profile defaults or embedded metadata. Pixel equality is evidence of matching
renders, NOT proof of neutral independence, source identity or training safety.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.lightroom_bridge import sp_auto01
from app.photographer.smart_preview_repeatability import compare_decoded_jpegs

SCHEMA = "prographer.spauto01.auto_vs_manual_reference.v1"
REPORT_DIR = "SP01_AUTO_REFERENCE_CHECK"
REPORT_NAME = "AUTO_VS_MANUAL_AGGREGATE.json"
MANUAL_RELATIVE = (
    Path("SP_01_Catalog_Test") / "SP_01_OFFLINE_PROOF"
    / "SP_01_OFFLINE_NEUTRAL_EXPORT" / "0H1A4577.jpg"
)


def compare_verified_auto_to_manual(*, root_override: Path | None = None) -> dict:
    ok, _ = sp_auto01.verify(root_override=root_override)
    if not ok:
        raise ValueError("unverified bridge job")
    root, _catalog, _smart, work = sp_auto01._context(root_override)
    state = sp_auto01._fields(work / "result.txt")
    auto = Path(state["jpeg"])
    manual = root / MANUAL_RELATIVE
    if manual.is_symlink() or not manual.is_file():
        raise ValueError("manual reference is missing or redirected")
    # No filenames or UUIDs from the Lightroom catalog are trusted as proof
    # that these are identical photographs. The same-photo assumption is a
    # private research attestation from the photographer.
    destination = work / REPORT_DIR
    if destination.is_symlink() or destination.exists():
        raise FileExistsError("reference report already exists; do not overwrite")
    outcome = compare_decoded_jpegs(auto, manual)
    aggregate = {
        "schema": SCHEMA,
        "status": "REFERENCE_RENDER_COMPARISON_COMPLETED",
        "manual_reference_is_human_attested_same_photo_NOT_SDK_VERIFIED": True,
        "auto_export_verified_by_bridge": True,
        "dimensions_match": outcome["dimensions_match"],
        "decoded_rgb_pixels_match": outcome["pixel_equal"],
        "mean_absolute_rgb_difference_8bit": outcome["mean_absolute_rgb_difference_8bit"],
        "max_absolute_rgb_difference_8bit": outcome["max_absolute_rgb_difference_8bit"],
        "fraction_pixels_all_channels_exact_match": outcome[
            "fraction_pixels_all_channels_exact_match"
        ],
        "byte_hashes_match": outcome["byte_hashes_match"],
        "render_equivalence_if_identical": (
            "CANDIDATE_SAME_RENDER" if outcome["pixel_equal"] else "REVIEW_EXPORT_POLICY_OR_BASELINE"
        ),
        "no_leakage_proven": False,
        "training_ready": False,
    }
    destination.mkdir()
    with (destination / REPORT_NAME).open("x", encoding="utf-8") as report:
        json.dump(aggregate, report, ensure_ascii=False, indent=2)
    return aggregate


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare verified auto JPEG to private manual research reference")
    parser.add_argument("--research-consent", action="store_true")
    parser.add_argument("--same-photo-manual-reference-confirmed", action="store_true")
    args = parser.parse_args()
    if not (args.research_consent and args.same_photo_manual_reference_confirmed):
        parser.error("local photographer research permission and same-photo identity must be confirmed")
    try:
        result = compare_verified_auto_to_manual()
    except (FileExistsError, ValueError, OSError, RuntimeError, MemoryError) as exc:
        parser.exit(2, f"SP-AUTO-01 REFERENCE CHECK STOPPED: {type(exc).__name__}\n")
    print("Auto-vs-manual reference comparison: COMPLETE")
    print("Decoded RGB pixels identical:", result["decoded_rgb_pixels_match"])
    print("Dimensions match:", result["dimensions_match"])
    print("Mean 8-bit RGB abs difference:", result["mean_absolute_rgb_difference_8bit"])
    print("No-leakage proven: False; training-ready: False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
