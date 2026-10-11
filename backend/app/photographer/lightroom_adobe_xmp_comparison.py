"""RAW-CAT-01E.03B.01: compare a PRIVATE catalog sample to Adobe-written XMP.

Research only: compares explicitly represented global Camera Raw properties,
not visual render parity, opaque masks/Look/.acr or source RAW provenance.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from app.photographer.develop_color_semantics import COLOR_FAMILIES
from app.photographer.raw_catalog_intake import _write_atomic

CRS = "{http://ns.adobe.com/camera-raw-settings/1.0/}"
RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
CURVES = ("ToneCurvePV2012", "ToneCurvePV2012Red",
          "ToneCurvePV2012Green", "ToneCurvePV2012Blue")


class XMPReferenceError(ValueError):
    pass


def xmp_global_fields(path: Path) -> dict:
    if path.suffix.lower() != ".xmp" or not path.is_file():
        raise XMPReferenceError("Adobe XMP file not found")
    raw = path.read_bytes()
    if len(raw) > 8_000_000 or b"<!DOCTYPE" in raw.upper():
        raise XMPReferenceError("unsupported XMP size or DTD")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise XMPReferenceError("invalid XML") from exc
    nodes = (root.findall(RDF + "Description") if root.tag == RDF + "RDF"
             else root.findall(".//" + RDF + "RDF/" + RDF + "Description"))
    if not nodes:
        raise XMPReferenceError("no RDF descriptions")
    result, duplicates = {}, set()

    def put(key, value):
        if key in result:
            duplicates.add(key)
        else:
            result[key] = value

    for node in nodes:
        for key, value in node.attrib.items():
            if key.startswith(CRS):
                put(key[len(CRS):], value)
        for child in node:
            if not child.tag.startswith(CRS):
                continue
            seq = child.find(RDF + "Seq")
            if seq is None:
                seq = child.find(RDF + "Bag")
            value = ([entry.text or "" for entry in seq.findall(RDF + "li")]
                     if seq is not None else child.text or "" if not len(child) else None)
            put(child.tag[len(CRS):], value)
    for key in duplicates:
        result[key] = None  # duplicated references cannot establish parity
    if not result:
        raise XMPReferenceError("no Camera Raw properties")
    return result


def xmp_curve(value):
    if isinstance(value, list):
        groups = [part.split(",") if isinstance(part, str) else [] for part in value]
    elif isinstance(value, str):
        tokens = value.split(",")
        groups = [tokens[i:i + 2] for i in range(0, len(tokens), 2)]
    else:
        return None
    if not 2 <= len(groups) <= 256:
        return None
    points = []
    for pair in groups:
        if len(pair) != 2:
            return None
        try:
            a, b = (float(v.strip()) for v in pair)
        except ValueError:
            return None
        if not all(math.isfinite(v) and v.is_integer() and 0 <= v <= 255 for v in (a, b)):
            return None
        points.append((int(a), int(b)))
    if any(points[i][0] >= points[i + 1][0] for i in range(len(points) - 1)):
        return None
    return tuple(points)


def equal_scalar(expected, actual):
    if not isinstance(actual, str):
        return None
    if isinstance(expected, bool):
        text = actual.strip().lower()
        return (expected == (text == "true")) if text in ("true", "false") else None
    if isinstance(expected, (int, float)):
        try:
            val = float(actual)
        except ValueError:
            return None
        return math.isclose(float(expected), val, rel_tol=0, abs_tol=.001) if math.isfinite(val) else None
    return expected == actual.strip() if isinstance(expected, str) else None


def group_for(field):
    if field in CURVES:
        return "point_curves"
    for family, keys in COLOR_FAMILIES.items():
        if field in keys:
            return family
    if field in ("CameraProfile", "WhiteBalance", "ProcessVersion", "ToneCurveName2012"):
        return "profile_context"
    return "basic_other"


def compare_sample(plan: dict, xmp: Path) -> dict:
    samples = plan.get("samples")
    if not isinstance(samples, list):
        raise XMPReferenceError("expected LOCAL PRIVATE 01E.03A plan")
    found = [s for s in samples if isinstance(s, dict)
             and str(s.get("file_stem", "")).casefold() == xmp.stem.casefold()
             and str(s.get("extension", "")).lower() == "cr3"]
    if len(found) != 1:
        raise XMPReferenceError("no unique matching selected CR3 sample")
    source = found[0]
    develop, curves = source.get("develop"), source.get("curves_and_opaque_structures")
    if not isinstance(develop, dict) or not isinstance(curves, dict):
        raise XMPReferenceError("private plan sample structure invalid")
    adobe = xmp_global_fields(xmp)
    status = {}
    by_family = defaultdict(Counter)

    def save(key, match):
        result = ("not_exported" if key not in adobe else
                  "uncomparable" if match is None else
                  "match" if match else "different")
        status[key] = result
        by_family[group_for(key)][result] += 1

    for name, value in sorted(develop.items()):
        save(name, equal_scalar(value, adobe[name]) if name in adobe else None)
    for name in CURVES:
        meta = curves.get(name)
        if not isinstance(meta, dict):
            continue
        if not meta.get("decoded"):
            status[name] = "catalog_curve_undecoded"
            by_family["point_curves"]["catalog_curve_undecoded"] += 1
            continue
        try:
            expected = tuple(tuple(int(v) for v in pair) for pair in meta["points"])
        except (KeyError, ValueError, TypeError) as exc:
            raise XMPReferenceError("invalid decoded curve") from exc
        actual = xmp_curve(adobe[name]) if name in adobe else None
        save(name, None if actual is None else actual == expected)
    totals = Counter(status.values())
    return {
        "schema": "prographer.adobe_xmp_reference_check.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ONE_SAMPLE_ADOBE_XMP_FIELD_RESEARCH",
        "privacy": "AGGREGATE ONLY; no photo identifiers, filenames, paths or settings values",
        "sample_matching": "unique filename stem in private CR3 sample plan; NOT identity proof",
        "result_counts": dict(sorted(totals.items())),
        "field_status": dict(sorted(status.items())),
        "by_family": {k: dict(sorted(v.items())) for k, v in sorted(by_family.items())},
        "additional_xmp_field_count_not_compared": len(set(adobe) - set(status)),
        "acr_auxiliary_present_unparsed": xmp.with_suffix(".acr").is_file(),
        "all_compared_expressions_matched": (
            totals.get("match", 0) > 0 and totals.get("different", 0) == 0
            and totals.get("uncomparable", 0) == 0),
        "adobe_visual_render_parity_verified": False,
        "opaque_masks_profile_look_parity_verified": False,
        "source_raw_identity_verified_by_comparator": False,
        "photographer_final_edit_confirmed": False,
        "training_ready_samples": 0,
        "warnings": [
            "Absent XMP properties are not explicit zeros or mismatches.",
            "Only global crs properties compared; local masks and .acr ignored.",
            "Matching field values or curves does not prove Lightroom rendering parity.",
            "Only one photo; matching names do not establish source provenance or finality.",
        ],
    }


def main() -> int:
    cli = argparse.ArgumentParser(description="PRIVATE plan vs Adobe-written XMP, aggregate output")
    cli.add_argument("--local-plan", type=Path, required=True)
    cli.add_argument("--xmp", type=Path, required=True)
    cli.add_argument("--report", type=Path, required=True)
    args = cli.parse_args()
    paths = [p.expanduser().resolve() for p in (args.local_plan, args.xmp, args.report)]
    if len(set(paths)) != 3 or paths[2].parent == paths[1].parent:
        cli.error("report must be separate from XMP/RAW folder and private input")
    try:
        plan = json.loads(args.local_plan.read_text(encoding="utf-8"))
        report = compare_sample(plan, args.xmp)
        _write_atomic(args.report, report)
    except (OSError, TypeError, ValueError) as exc:
        cli.exit(2, "XMP comparison FAILED; inputs unchanged: " + type(exc).__name__ + "\n")
    print("Aggregate report:", args.report)
    print("Outcomes:", report["result_counts"])
    print("Adobe renderer/masks parity: NOT VERIFIED; training-ready: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
