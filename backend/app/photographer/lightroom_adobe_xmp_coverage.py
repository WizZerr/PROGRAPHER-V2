"""RAW-CAT-01E.03B.02: aggregate-only inventory of untested Adobe XMP fields.

Lists Camera Raw XML property names, never values or photographer identifiers.
Lexical family labels are triage hints, NOT Adobe edit semantics.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from app.photographer.lightroom_adobe_xmp_comparison import (
    compare_sample, xmp_global_fields,
)
from app.photographer.raw_catalog_intake import _write_atomic

SAFE_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,119}$")
FAMILIES = (
    ("local_masks_retouch", ("Mask", "Correction", "Retouch", "Remove", "RedEye")),
    ("look_and_profile", ("Look", "Profile", "Camera", "Preset")),
    ("crop_geometry", ("Crop", "Perspective", "Upright", "Lens", "Transform", "Rotate", "Angle")),
    ("detail_noise", ("Sharp", "Noise", "Luminance", "Grain", "Defringe", "Chromatic")),
    ("color_and_tone", ("Color", "Hue", "Saturation", "Tone", "Curve", "Split", "Gray", "Grayscale")),
)


def lexical_family(key: str) -> str:
    for label, prefixes in FAMILIES:
        if key.startswith(prefixes):
            return label
    return "other_unclassified"


def audit_uncompared_properties(private_plan: dict, xmp: Path) -> dict:
    parity = compare_sample(private_plan, xmp)
    props = xmp_global_fields(xmp)
    compared = set(parity["field_status"])
    extras = {k: v for k, v in props.items() if k not in compared}
    safe_keys = sorted(k for k in extras if SAFE_KEY.fullmatch(k))
    unsafe_count = len(extras) - len(safe_keys)
    families: dict[str, list[str]] = {}
    forms: Counter[str] = Counter()
    for key in safe_keys:
        family = lexical_family(key)
        families.setdefault(family, []).append(key)
        value = extras[key]
        forms["text_scalar" if isinstance(value, str) else
              "sequence_shallow" if isinstance(value, list) else
              "nested_or_ambiguous"] += 1
    return {
        "schema": "prographer.adobe_xmp_coverage_audit.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "RESEARCH_UNCOMPARED_XMP_PROPERTY_NAMES_ONLY",
        "privacy": "PROPERTY NAMES ONLY; no values, paths, photo IDs, image names or pixels",
        "compared_property_count": len(compared),
        "compared_match_count": parity["result_counts"].get("match", 0),
        "compared_different_count": parity["result_counts"].get("different", 0),
        "not_exported_count": parity["result_counts"].get("not_exported", 0),
        "xmp_total_global_camera_raw_property_count": len(props),
        "uncompared_property_count": len(extras),
        "unlisted_nonstandard_property_key_count": unsafe_count,
        "uncompared_property_structure_count": dict(sorted(forms.items())),
        "lexical_family_keys": {k: families[k] for k in sorted(families)},
        "lexical_family_counts": {k: len(families[k]) for k in sorted(families)},
        "opaque_mask_and_acr_values_interpreted": False,
        "profile_look_adobe_semantics_verified": False,
        "render_parity_verified": False,
        "training_ready_samples": 0,
        "warnings": [
            "Lexical field categories do not imply decoded Lightroom edit semantics.",
            "Only top-level Camera Raw property names inspected; no mask-local values.",
            "48 matches were per-field comparisons within ONE photo, not 48 photos.",
            "XMP and .acr presence do not establish Adobe rendering or mask/profile parity.",
            "No validated photographer finality, event partitions, or Brain training readiness.",
        ],
    }


def main() -> int:
    cli = argparse.ArgumentParser(description="Local-only audit of untested Adobe XMP field names")
    cli.add_argument("--local-plan", type=Path, required=True)
    cli.add_argument("--xmp", type=Path, required=True)
    cli.add_argument("--report", type=Path, required=True)
    args = cli.parse_args()
    paths = [p.expanduser().resolve() for p in (args.local_plan, args.xmp, args.report)]
    if len(set(paths)) != 3 or paths[2].parent == paths[1].parent:
        cli.error("report must be outside original XMP/RAW directory and private inputs")
    try:
        plan = json.loads(args.local_plan.read_text(encoding="utf-8"))
        report = audit_uncompared_properties(plan, args.xmp)
        _write_atomic(args.report, report)
    except (OSError, ValueError, TypeError) as exc:
        cli.exit(2, "Adobe XMP coverage audit FAILED; inputs untouched: " + type(exc).__name__ + "\n")
    print("Aggregate report:", args.report)
    print("Untested Adobe XMP property count:", report["uncompared_property_count"])
    print("Adobe render/mask parity and training: NOT VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
