"""RAW-CAT-01E.03A: privacy-separated Lightroom manual validation sample plan.

Research / coverage planning ONLY. This selects candidate rows from a copied
Lightroom catalog, without changing source/catalog or verifying Adobe parity.
All sample filenames/values stay in the explicitly PRIVATE local plan.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json

from app.photographer.develop_color_semantics import (
    COLOR_FAMILIES, GRADING_CONFIGURATION_FIELDS, OPAQUE_LOCAL_FIELDS,
)
from app.photographer.raw_catalog_intake import _write_atomic, inspect_catalog

SCHEMA = "prographer.raw_catalog_validation_plan.v1"
CATEGORIES = (
    "linear_curve_reference",
    "nonlinear_tone_curve",
    "nonlinear_rgb_channel_curve",
    "hsl_mixer_adjustment_candidate",
    "grayscale_conversion",
    "grayscale_mixer_adjustment_candidate",
    "color_grading_adjustment_candidate",
    "legacy_split_toning_adjustment_candidate",
    "mask_payload_unverified",
    "retouch_payload_unverified",
)


def classify_sample(record: dict) -> tuple[str, ...]:
    """Report evidence categories, never a claim of active/final edits."""
    if record.get("parse_exclusion") or record.get("status") == "quarantined":
        return ()
    develop = record.get("develop") or {}
    complex_fields = record.get("complex") or {}
    classifications: list[str] = []

    tone = complex_fields.get("ToneCurvePV2012", {})
    if tone.get("decoded") and tone.get("is_linear") is True:
        classifications.append("linear_curve_reference")
    if tone.get("decoded") and tone.get("is_linear") is False:
        classifications.append("nonlinear_tone_curve")
    if any(
        complex_fields.get("ToneCurvePV2012" + channel, {}).get("decoded")
        and complex_fields.get("ToneCurvePV2012" + channel, {}).get("is_linear") is False
        for channel in ("Red", "Green", "Blue")
    ):
        classifications.append("nonlinear_rgb_channel_curve")

    if any(develop.get(k, 0) != 0 for k in COLOR_FAMILIES["hsl_mixer"] if k in develop):
        classifications.append("hsl_mixer_adjustment_candidate")
    if develop.get("ConvertToGrayscale") is True:
        classifications.append("grayscale_conversion")
    if any(develop.get(k, 0) != 0 for k in COLOR_FAMILIES["grayscale_mixer"] if k in develop):
        classifications.append("grayscale_mixer_adjustment_candidate")
    if any(
        develop.get(k, 0) != 0 for k in
        (COLOR_FAMILIES["color_grading"] - GRADING_CONFIGURATION_FIELDS) if k in develop
    ):
        classifications.append("color_grading_adjustment_candidate")
    if any(
        develop.get(k, 0) != 0 for k in COLOR_FAMILIES["legacy_split_toning"] if k in develop
    ):
        classifications.append("legacy_split_toning_adjustment_candidate")

    if complex_fields.get("MaskGroupBasedCorrections", {}).get("structure_nonempty"):
        classifications.append("mask_payload_unverified")
    if any(
        complex_fields.get(k, {}).get("structure_nonempty")
        for k in ("RetouchAreas", "RemoveAreas", "RetouchInfo")
    ):
        classifications.append("retouch_payload_unverified")
    return tuple(classifications)


def build_validation_plan(records: list[dict], *, per_category: int = 2) -> tuple[dict, dict]:
    """Select bounded diverse rows. Never write photo identifiers to aggregate."""
    if not 1 <= per_category <= 5:
        raise ValueError("per_category must be 1..5")
    categories = [(rec, classify_sample(rec)) for rec in records]
    candidate_counts: Counter[str] = Counter()
    for _, tags in categories:
        candidate_counts.update(tags)

    selected: dict[object, dict] = {}
    selected_groups: Counter[str] = Counter()
    for category in CATEGORIES:
        candidates = [
            rec for rec, tags in categories
            if category in tags and rec.get("catalog_image_id") not in selected
        ]
        candidates.sort(key=lambda r: (
            selected_groups.get(str(r.get("event_group_id")), 0),
            str(r.get("event_group_id", "")),
            int(r.get("catalog_image_id") or 0),
        ))
        for rec in candidates[:per_category]:
            image_id = rec.get("catalog_image_id")
            selected[image_id] = rec
            selected_groups[str(rec.get("event_group_id"))] += 1

    local_samples: list[dict] = []
    selected_tag_counts: Counter[str] = Counter()
    for rec in selected.values():
        tags = classify_sample(rec)
        selected_tag_counts.update(tags)
        # Private! Includes filenames & individual Develop metadata.
        local_samples.append({
            "catalog_image_id": rec.get("catalog_image_id"),
            "file_stem": rec.get("file_stem"),
            "extension": rec.get("extension"),
            "candidate_group_id": rec.get("event_group_id"),
            "evidence_categories": list(tags),
            "develop": rec.get("develop", {}),
            "curves_and_opaque_structures": rec.get("complex", {}),
            "source_raw_verified": False,
            "final_edit_confirmed": False,
            "lightroom_parity_verified": False,
            "training_eligible": False,
        })

    report = {
        "schema": SCHEMA,
        "status": "RESEARCH_SAMPLE_SELECTION_ONLY",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "privacy": "AGGREGATE ONLY; no photo identifiers, filenames, paths, dates or Develop values",
        "catalog_raw_rows_considered": len(records),
        "category_candidate_counts": {key: candidate_counts[key] for key in CATEGORIES},
        "requested_per_category": per_category,
        "selected_unique_photo_count": len(selected),
        "selected_category_coverage": {key: selected_tag_counts[key] for key in CATEGORIES},
        "selected_candidate_group_count": len(selected_groups),
        "training_ready_samples": 0,
        "warnings": [
            "Selections are catalog evidence, NOT photographer-approved events or final edits",
            "Lightroom controls must be checked in Adobe Lightroom Classic independently",
            "No Lightroom/Adobe XMP parity or RAW source matching was performed",
            "Candidate group IDs are provisional; no event-level split is established",
        ],
    }
    private = {
        "schema": SCHEMA,
        "privacy": "LOCAL PRIVATE ONLY — FILENAMES, PHOTO IDS, DEVELOP VALUES; DO NOT UPLOAD",
        "workflow": "Open a COPY of the catalog in Lightroom Classic; inspect only, do not modify or sync; manually compare Develop values, curves, HSL, and mask presence",
        "training_ready_samples": 0,
        "samples": local_samples,
    }
    return report, private


def main() -> int:
    cli = argparse.ArgumentParser(description="RAW-CAT-01E.03A read-only Lightroom comparison sample selector")
    cli.add_argument("--catalog", type=Path, required=True)
    cli.add_argument("--report", type=Path, required=True, help="shareable aggregate JSON")
    cli.add_argument("--local-plan", type=Path, required=True, help="PRIVATE photo-level plan — keep local")
    cli.add_argument("--per-category", type=int, default=2)
    args = cli.parse_args()
    resolved = [p.resolve() for p in (args.catalog, args.report, args.local_plan)]
    if len(set(resolved)) != 3:
        cli.error("catalog, aggregate report and local private plan paths must differ")
    try:
        _, private_manifest = inspect_catalog(args.catalog, include_private=True)
        if private_manifest is None:
            raise ValueError("missing local photo records")
        report, local = build_validation_plan(private_manifest["records"], per_category=args.per_category)
        # Write private selection FIRST to avoid a misleading shareable success
        # report when writing the required local inspection plan fails.
        _write_atomic(args.local_plan, local)
        _write_atomic(args.report, report)
    except (ValueError, OSError) as exc:
        cli.exit(2, "RAW-CAT-01E.03A FAILED (source unchanged): " + str(exc) + "\n")
    print("Aggregate report:", args.report)
    print("Selected unique catalog photo candidates:", report["selected_unique_photo_count"])
    print("Local PRIVATE inspection plan (DO NOT UPLOAD):", args.local_plan)
    print("Lightroom parity verified: NO; training-ready samples: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
