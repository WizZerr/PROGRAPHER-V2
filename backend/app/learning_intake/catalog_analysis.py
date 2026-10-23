"""One-step catalog analysis for the photographer-facing flow: stages 3-5 in a single pass.

Links Smart Previews to catalog photos (PG-LI-03), reads the photographer's edits as before/after pairs
(PG-LI-04), summarises the photographer's style, and measures the anchor method (PG-LI-05) to say how much work
it could save. The summary holds only numbers, so it can be stored with the profile; the sample "before" images
are returned once, for display, and never stored. Nothing here is training-ready or applied to Lightroom.
"""
from __future__ import annotations

from typing import Any

from app.learning_intake.anchor_backtest import ANCHOR_CURVE, predict, prepare, score, UNTOUCHED
from app.learning_intake.edit_pairs import TARGETS, build_pairs
from app.learning_intake.smart_preview_link import LINKED_VERIFIED, build_links

DEFAULT_ANCHORS = 100
SAMPLES = 4


def _style(coverage: dict[str, dict], pairs: int) -> list[dict]:
    """Per slider: what the photographer does with it across the catalog: a fixed value (preset), adjusted per
    photo, left at 0, or used only on a minority of photos ("rare", e.g. Dehaze on 1 photo of 3,184)."""
    style = []
    for key in TARGETS:
        c = coverage.get(key) or {}
        if not c.get("present"):
            continue
        fixed = c["p10"] == c["p90"]
        kind = ("rare" if c["present"] < 0.5 * pairs else "untouched" if fixed and c["median"] == 0
                else "fixed" if fixed else "per_photo")
        style.append({"key": key, "kind": kind, "median": c["median"], "p10": c["p10"], "p90": c["p90"],
                      "present": c["present"]})
    return style


def analyze(preview_root, records: list[dict], *, anchors: int = DEFAULT_ANCHORS) -> dict[str, Any]:
    from app.learning_intake.smart_preview_probe import _count_dng_files, _decode_sample

    _counts, dngs = _count_dng_files(preview_root)
    links = build_links(dngs, records)
    pairs_result = build_pairs(links["links"])
    rows, excluded, check = prepare(pairs_result["pairs"])
    k = min(anchors, len(rows) // 5)
    savings: dict[str, Any] = {"anchors": k, "photos": len(rows), "untouched_definition": UNTOUCHED}
    samples: list[dict] = []
    if k >= 1:
        run = predict(rows, k)
        results = {name: score(preds) for name, preds in run["methods"].items()}
        savings.update({
            "proposed_photos": results["anchors"]["photos"],
            "untouched_pct": results["anchors"]["untouched_pct"],
            "no_correction_untouched_pct": results["as_shot"]["untouched_pct"],
            "exposure_ok_pct": results["anchors"]["exposure_ok_pct"],
            "temperature_ok_pct": results["anchors"]["temperature_ok_pct"],
            "tint_ok_pct": results["anchors"]["tint_ok_pct"],
            "curve": [{"anchors": c, "untouched_pct": score(predict(rows, c)["methods"]["anchors"])["untouched_pct"]}
                      for c in sorted({*ANCHOR_CURVE, k}) if 1 <= c <= len(rows) // 5],
        })
        preds = run["methods"]["anchors"]
        for p in [preds[i * len(preds) // SAMPLES] for i in range(min(SAMPLES, len(preds)))]:
            row = rows[p["index"]]
            decoded = _decode_sample(row["dng"])
            samples.append({
                "file_name": row["file_name"],
                "photographer": {"exposure": row["exposure"], "temperature_k": round(row["targets"]["Temperature"]),
                                 "tint": round(row["targets"]["Tint"])},
                "proposed": {"exposure": round(p["exposure"], 2), "temperature_k": round(1.0e6 / p["mired"]),
                             "tint": round(p["tint"])},
                "untouched": all(abs(e) <= lim for e, lim in zip(p["err"], UNTOUCHED.values())),
                "thumbnail_jpeg_base64": (decoded.get("reset_render") or {}).get("thumbnail_jpeg_base64"),
                "width": (decoded.get("reset_render") or {}).get("width"),
                "height": (decoded.get("reset_render") or {}).get("height"),
            })
    summary = {
        "schema": "prographer.learning_intake.catalog_analysis.v1",
        "photos": len(records),
        "smart_preview_files": len(dngs),
        "linked": links["status_counts"].get(LINKED_VERIFIED, 0),
        "link_status_counts": links["status_counts"],
        "pairs": pairs_result["pairs_for_review"],
        "pair_exclusions": pairs_result["excluded_counts"],
        "other_edit_counts": pairs_result["other_edit_counts"],
        "folder_groups": len(pairs_result["folder_groups"]),
        "style": _style(pairs_result["target_coverage"], pairs_result["pairs_for_review"]),
        "backtest_exclusions": excluded,
        "as_shot_conversion_check": check,
        "savings": savings,
        "training_ready_samples": 0,
    }
    return {"summary": summary, "samples": samples}
