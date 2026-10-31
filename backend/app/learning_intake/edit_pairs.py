"""PG-LI-04 — "before / after" pairs: a linked Smart Preview (before) with the photographer's Develop values (after).

Built on PG-LI-03 links. Only name-verified links are used. Values come from the catalog's own Develop record,
parsed by raw_catalog_intake.parse_develop_settings (no Lua executed); a field that is absent stays absent. It
is never treated as zero (e.g. Dehaze appeared in only 19 of 5,210 research photos).
Lessons from the research pilot kept here:
  - each shooter's folder starts from a different preset, so values are summarised per folder group;
  - temperature is compared in mired (1e6 / Kelvin), not Kelvin;
  - virtual copies share one "before" image, so they are not separate examples.
Read only and transient: pairs are returned in memory for review, never stored, and never training-ready
(edit finality and whole-event validation splits are not established).
"""
from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any

from app.learning_intake.smart_preview_link import LINKED_VERIFIED
from app.photographer.develop_color_semantics import COLOR_FIELDS, GRADING_CONFIGURATION_FIELDS

# Global sliders a style model can predict from the "before" image. Order = display order.
TARGETS = ("Exposure2012", "Contrast2012", "Highlights2012", "Shadows2012", "Whites2012", "Blacks2012",
           "Texture", "Clarity2012", "Dehaze", "Vibrance", "Saturation", "Temperature", "Tint")
CURVES = ("ToneCurvePV2012", "ToneCurvePV2012Red", "ToneCurvePV2012Green", "ToneCurvePV2012Blue")


def _other_edits(rec: dict) -> dict[str, bool]:
    """Edits outside the global sliders: kept as flags so a later stage can decide, never as fake numbers."""
    develop, complex_fields = rec.get("develop") or {}, rec.get("complex") or {}
    # HSL / gray mixer / colour grading only; Blending and Balance are configuration, not an edit.
    numeric_color = [v for k, v in develop.items() if k in COLOR_FIELDS and k not in GRADING_CONFIGURATION_FIELDS
                     and isinstance(v, (int, float)) and not isinstance(v, bool)]
    return {
        "tone_curve": any(complex_fields.get(c, {}).get("decoded") and not complex_fields[c].get("is_linear")
                          for c in CURVES),
        "color_adjustments": any(v != 0 for v in numeric_color),
        "local_or_opaque_edits": bool(rec.get("opaque_edit_review_required")),
        "black_and_white": develop.get("ConvertToGrayscale") is True or rec.get("grayscale") is True,
    }


def build_pairs(links: list[dict]) -> dict[str, Any]:
    """Private pairs (with DNG paths) plus aggregate evidence, from build_links() output."""
    pairs: list[dict[str, Any]] = []
    excluded: Counter[str] = Counter()
    for link in links:
        rec = link["record"]
        if link["status"] != LINKED_VERIFIED:
            excluded["link_not_verified"] += 1
            continue
        if link["virtual_copy_candidate"]:
            excluded["virtual_copy_shares_master_preview"] += 1
            continue
        if rec.get("parse_exclusion"):
            excluded[str(rec["parse_exclusion"])] += 1
            continue
        if rec.get("pick") is not None and float(rec["pick"]) < 0:
            excluded["rejected_in_lightroom"] += 1
            continue
        develop = rec.get("develop") or {}
        targets = {k: float(develop[k]) for k in TARGETS if isinstance(develop.get(k), (int, float))}
        if not targets:
            excluded["no_global_develop_values"] += 1
            continue
        temperature = targets.get("Temperature")
        pairs.append({
            "dng": link["dng"],
            "file_name": f"{rec.get('file_stem')}.{rec.get('extension')}",
            "folder_key": (rec.get("catalog_root_name"), rec.get("catalog_folder")),
            "capture_day": rec.get("capture_day"),
            "capture_time": rec.get("capture_time"),
            "targets": targets,
            "temperature_mired": round(1e6 / temperature, 1) if temperature and temperature > 0 else None,
            "white_balance": develop.get("WhiteBalance"),
            "missing_targets": [k for k in TARGETS if k not in targets],
            "other_edits": _other_edits(rec),
            "pick": rec.get("pick"),
            "rating": rec.get("rating"),
            "flash": rec.get("flash"),
        })

    # Folder groups get neutral labels (folder names can hold the couple's names), largest first.
    sizes = Counter(p["folder_key"] for p in pairs)
    labels = {key: f"F{i:02d}" for i, (key, _n) in enumerate(sizes.most_common(), 1)}
    for p in pairs:
        p["folder_group"] = labels[p["folder_key"]]

    def stats(values: list[float]) -> dict[str, float] | None:
        if not values:
            return None
        v = sorted(values)
        return {"median": round(median(v), 3), "p10": round(v[int(0.1 * (len(v) - 1))], 3),
                "p90": round(v[int(0.9 * (len(v) - 1))], 3)}

    # The style numbers describe the colour edits: photos turned black & white serve another look.
    colour = [p for p in pairs if not p["other_edits"]["black_and_white"]]
    coverage = {k: {"present": sum(k in p["targets"] for p in colour),
                    **(stats([p["targets"][k] for p in colour if k in p["targets"]]) or {})} for k in TARGETS}
    groups = []
    for key, label in sorted(labels.items(), key=lambda kv: kv[1]):
        members = [p for p in colour if p["folder_key"] == key]
        groups.append({
            "folder_group": label,
            "pairs": len(members),
            "exposure_median": (stats([p["targets"]["Exposure2012"] for p in members if "Exposure2012" in p["targets"]])
                                or {}).get("median"),
            "temperature_mired_median": (stats([p["temperature_mired"] for p in members if p["temperature_mired"]])
                                         or {}).get("median"),
            "tint_median": (stats([p["targets"]["Tint"] for p in members if "Tint" in p["targets"]]) or {}).get("median"),
        })
    return {
        "pairs": pairs,
        "pairs_for_review": len(pairs),
        "colour_pairs": len(colour),
        "excluded_counts": dict(sorted(excluded.items())),
        "target_coverage": coverage,
        "other_edit_counts": {k: sum(p["other_edits"][k] for p in pairs)
                              for k in ("tone_curve", "color_adjustments", "local_or_opaque_edits", "black_and_white")},
        "folder_groups": groups,
    }


def pairs_report(preview_root, records: list[dict], *, sample_size: int = 4) -> dict[str, Any]:
    """Aggregate pair evidence plus up to `sample_size` pairs shown as before image + photographer values."""
    from app.learning_intake.smart_preview_link import build_links
    from app.learning_intake.smart_preview_probe import _count_dng_files, _decode_sample

    _counts, dngs = _count_dng_files(preview_root)
    result = build_pairs(build_links(dngs, records)["links"])
    pairs = result["pairs"]
    picks = [pairs[i * len(pairs) // sample_size] for i in range(min(sample_size, len(pairs)))] if sample_size else []
    samples = []
    for pair in picks:
        decoded = _decode_sample(pair["dng"])
        samples.append({
            "file_name": pair["file_name"],
            "folder_group": pair["folder_group"],
            "capture_day": pair["capture_day"],
            "targets": pair["targets"],
            "temperature_mired": pair["temperature_mired"],
            "white_balance": pair["white_balance"],
            "other_edits": pair["other_edits"],
            "decode_state": decoded.get("state"),
            "reset_render": decoded.get("reset_render"),
        })
    return {
        "schema": "prographer.learning_intake.edit_pairs.v1",
        "status": "BEFORE_AFTER_PAIRS_RESEARCH_ONLY",
        "catalog_raw_records": len(records),
        **{k: v for k, v in result.items() if k != "pairs"},
        "targets": list(TARGETS),
        "samples": samples,
        "photographer_finality_verified": False,
        "training_ready_samples": 0,
        "warnings": [
            "'After' values are the catalog's current Develop settings; whether they are the photographer's final, delivered edit is not verified.",
            "A field missing from the catalog is reported as missing, never as zero.",
            "Folder groups are labelled F01, F02... (largest first); shooters with different presets show up as groups with different medians.",
            "Pairs are built in memory for review and are not stored; no sample is training-ready.",
        ],
    }
