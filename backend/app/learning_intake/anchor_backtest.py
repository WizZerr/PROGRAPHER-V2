"""PG-LI-05 — style model backtest: the research "anchor" method replayed on the product's own before/after pairs.

Workflow it simulates: the photographer edits K anchor photos of an event, the system proposes the rest.
  - Photos are put in capture-time order and cut into K consecutive runs; the middle photo of each run is its anchor.
  - Exposure: copy the run's anchor (research: the gap is the anchor's value, not the segmentation).
  - White balance: follow the camera. The anchor's change from ITS As Shot (in mired, and in tint) is applied on
    top of each photo's own As Shot (research HYBRID rule), so a lighting change the camera saw carries through.
Compared with two baselines on the same non-anchor photos:
  - "as_shot":       no correction at all (exposure 0, white balance As Shot);
  - "global_median": the median of the anchors' exposure and white-balance changes, applied to every photo.
"Untouched" = the photographer would not need to touch it: |exposure| <= 0.15 EV, |temperature| <= 5 mired and
|tint| <= 2, the research definition. Black-and-white photos are left out (white balance does not apply).

Research only: nothing is stored, no model file is written, nothing is applied to Lightroom, and the gates for
training on real data (consent, finality, unseen-event test) are not changed by this report.
"""
from __future__ import annotations

from statistics import median
from typing import Any

UNTOUCHED = {"exposure": 0.15, "mired": 5.0, "tint": 2.0}
ANCHOR_CURVE = (15, 50, 100)


def _mired(kelvin: float) -> float:
    return 1.0e6 / kelvin


def prepare(pairs: list[dict]) -> tuple[list[dict], dict[str, int], dict[str, Any]]:
    """Add As Shot white balance and the photographer's changes to each pair; returns rows, exclusions and the
    As Shot conversion check (our conversion vs the value Lightroom stored for "As Shot" photos)."""
    from app.learning_intake.white_balance import as_shot_temperature_tint, read_wb_tags

    rows, excluded = [], {}
    check_k, check_tint = [], []

    def skip(reason: str) -> None:
        excluded[reason] = excluded.get(reason, 0) + 1

    for pair in pairs:
        t = pair["targets"]
        if pair["other_edits"].get("black_and_white"):
            skip("black_and_white")
            continue
        if not {"Exposure2012", "Temperature", "Tint"} <= t.keys() or t["Temperature"] <= 0:
            skip("missing_exposure_or_white_balance")
            continue
        try:
            shot_k, shot_tint = as_shot_temperature_tint(read_wb_tags(pair["dng"]))
        except Exception:  # noqa: BLE001
            skip("as_shot_unreadable")
            continue
        as_shot = str(pair.get("white_balance") or "").casefold() == "as shot"
        if as_shot:  # Lightroom stored its own As Shot conversion here: measures ours
            check_k.append(abs(shot_k - t["Temperature"]))
            check_tint.append(abs(shot_tint - t["Tint"]))
        # The same conversion is used for every photo, so a small systematic offset in it cancels out between an
        # anchor and the photos it is applied to (for As Shot photos the change is that offset, ~0).
        d_mired, d_tint = _mired(t["Temperature"]) - _mired(shot_k), t["Tint"] - shot_tint
        rows.append({**pair, "as_shot_k": shot_k, "as_shot_tint": shot_tint, "d_mired": d_mired, "d_tint": d_tint,
                     "exposure": t["Exposure2012"], "wb_as_shot": as_shot})
    rows.sort(key=lambda r: (r.get("capture_time") or "", r["file_name"]))

    def q(values: list[float], p: float) -> float | None:
        return round(sorted(values)[int(p * (len(values) - 1))], 1) if values else None

    check = {"as_shot_photos": len(check_k), "median_abs_kelvin": q(check_k, 0.5), "p90_abs_kelvin": q(check_k, 0.9),
             "median_abs_tint": q(check_tint, 0.5), "p90_abs_tint": q(check_tint, 0.9)}
    return rows, dict(sorted(excluded.items())), check


def _anchor_indices(n: int, k: int) -> list[int]:
    """Middle photo of each of k consecutive, equal-count runs."""
    return [(i * n // k + (i + 1) * n // k - 1) // 2 for i in range(k)]


def predict(rows: list[dict], k: int) -> dict[str, Any]:
    n = len(rows)
    anchors = _anchor_indices(n, k)
    run_of = [run for run in range(k) for _ in range(run * n // k, (run + 1) * n // k)]
    anchor_set = set(anchors)
    med = {key: median(rows[a][key] for a in anchors) for key in ("exposure", "d_mired", "d_tint")}
    methods: dict[str, list[dict]] = {"anchors": [], "global_median": [], "as_shot": []}
    for i, row in enumerate(rows):
        if i in anchor_set:
            continue
        a = rows[anchors[run_of[i]]]
        shot = _mired(row["as_shot_k"])
        guesses = {
            "anchors": (a["exposure"], shot + a["d_mired"], row["as_shot_tint"] + a["d_tint"]),
            "global_median": (med["exposure"], shot + med["d_mired"], row["as_shot_tint"] + med["d_tint"]),
            "as_shot": (0.0, shot, row["as_shot_tint"]),
        }
        truth = (row["exposure"], shot + row["d_mired"], row["as_shot_tint"] + row["d_tint"])
        for name, (exp, mired, tint) in guesses.items():
            methods[name].append({"index": i, "exposure": exp, "mired": mired, "tint": tint,
                                  "err": (exp - truth[0], mired - truth[1], tint - truth[2])})
    return {"k": k, "anchors": anchors, "methods": methods}


def score(predictions: list[dict]) -> dict[str, Any]:
    if not predictions:
        return {"photos": 0}
    within = [(abs(p["err"][0]) <= UNTOUCHED["exposure"], abs(p["err"][1]) <= UNTOUCHED["mired"],
               abs(p["err"][2]) <= UNTOUCHED["tint"]) for p in predictions]
    n = len(predictions)

    def pct(values) -> float:
        return round(100.0 * sum(values) / n, 1)

    return {
        "photos": n,
        "untouched_pct": pct(all(w) for w in within),
        "exposure_ok_pct": pct(w[0] for w in within),
        "temperature_ok_pct": pct(w[1] for w in within),
        "tint_ok_pct": pct(w[2] for w in within),
        "exposure_mae": round(sum(abs(p["err"][0]) for p in predictions) / n, 3),
        "mired_mae": round(sum(abs(p["err"][1]) for p in predictions) / n, 2),
        "tint_mae": round(sum(abs(p["err"][2]) for p in predictions) / n, 2),
    }


def backtest_report(preview_root, records: list[dict], *, anchors: int = 100, sample_size: int = 4) -> dict[str, Any]:
    from app.learning_intake.edit_pairs import build_pairs
    from app.learning_intake.smart_preview_link import build_links
    from app.learning_intake.smart_preview_probe import _count_dng_files, _decode_sample

    _counts, dngs = _count_dng_files(preview_root)
    pairs = build_pairs(build_links(dngs, records)["links"])["pairs"]
    rows, excluded, check = prepare(pairs)
    usable_k = min(anchors, len(rows) // 5)
    result: dict[str, Any] = {
        "schema": "prographer.learning_intake.anchor_backtest.v1",
        "status": "STYLE_MODEL_BACKTEST_RESEARCH_ONLY",
        "pairs": len(pairs),
        "photos_in_backtest": len(rows),
        "excluded_counts": excluded,
        "as_shot_conversion_check": check,
        "untouched_definition": UNTOUCHED,
        "anchors_requested": anchors,
        "anchors_used": usable_k,
        "results": {},
        "anchor_curve": [],
        "samples": [],
        "model_stored": False,
        "applied_to_lightroom": False,
        "training_ready_samples": 0,
        "warnings": [
            "Backtest inside one catalog: the anchors are real photographer edits from the same event, as in the anchor workflow. It is not an unseen-event generalisation test.",
            "Anchors are the middle photo of equal-count runs in capture-time order; real anchor choice may differ.",
            "'After' values are the catalog's current Develop settings; edit finality is not verified.",
            "Nothing is stored or applied; this is a measurement, not a trained model.",
        ],
    }
    if usable_k < 1:
        result["warnings"].insert(0, "Too few usable photos for a backtest (need at least 5 per anchor).")
        return result
    run = predict(rows, usable_k)
    result["results"] = {name: score(preds) for name, preds in run["methods"].items()}
    for k in sorted({*ANCHOR_CURVE, usable_k}):
        if 1 <= k <= len(rows) // 5:
            result["anchor_curve"].append({"anchors": k, **{
                name: score(preds)["untouched_pct"] for name, preds in predict(rows, k)["methods"].items()}})
    preds = run["methods"]["anchors"]
    for p in [preds[i * len(preds) // sample_size] for i in range(min(sample_size, len(preds)))] if sample_size else []:
        row = rows[p["index"]]
        decoded = _decode_sample(row["dng"])
        result["samples"].append({
            "file_name": row["file_name"],
            "photographer": {"exposure": row["exposure"], "temperature_k": round(row["targets"]["Temperature"]),
                             "tint": round(row["targets"]["Tint"]), "white_balance": row.get("white_balance")},
            "proposed": {"exposure": round(p["exposure"], 2), "temperature_k": round(1.0e6 / p["mired"]),
                         "tint": round(p["tint"])},
            "untouched": abs(p["err"][0]) <= UNTOUCHED["exposure"] and abs(p["err"][1]) <= UNTOUCHED["mired"]
                         and abs(p["err"][2]) <= UNTOUCHED["tint"],
            "decode_state": decoded.get("state"),
            "reset_render": decoded.get("reset_render"),
        })
    return result
