from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.datasets.jpeg_integrity import load_and_validate_dataset_snapshot
from jpeg_j0_feasibility import (
    _apply_recipe_uint8,
    _match_geometry,
    _read_image,
    _write_jpeg,
)
from jpeg_j1_synthetic_brain import (
    FEATURE_NAMES,
    _restore_recipe,
    extract_features,
)


SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _image_metrics(
    predicted: np.ndarray,
    target: np.ndarray,
) -> tuple[float, float, float]:
    error = predicted.astype(np.float32) - target.astype(np.float32)
    mae = float(np.mean(np.abs(error)))
    rmse = float(np.sqrt(np.mean(np.square(error))))
    psnr = float("inf") if rmse <= 1e-12 else 20.0 * math.log10(255.0 / rmse)
    return mae, rmse, psnr


def _fit_tile(image: np.ndarray, width: int, height: int) -> np.ndarray:
    ih, iw = image.shape[:2]
    scale = min(width / float(iw), height / float(ih))
    resized = cv2.resize(
        image,
        (max(1, round(iw * scale)), max(1, round(ih * scale))),
        interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC,
    )
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    rh, rw = resized.shape[:2]
    x = (width - rw) // 2
    y = (height - rh) // 2
    canvas[y : y + rh, x : x + rw] = resized
    return canvas


def _comparison_row(
    original: np.ndarray,
    photographer: np.ndarray,
    prediction: np.ndarray,
    mean_baseline: np.ndarray,
    *,
    label: str,
    mae: float,
) -> np.ndarray:
    tile_w = 320
    tile_h = 220
    header_h = 44
    footer_h = 32
    labels = ("ORIGINAL", "PHOTOGRAPHER", "FROZEN CANDIDATE", "MEAN RECIPE")
    tiles = [
        _fit_tile(original, tile_w, tile_h),
        _fit_tile(photographer, tile_w, tile_h),
        _fit_tile(prediction, tile_w, tile_h),
        _fit_tile(mean_baseline, tile_w, tile_h),
    ]

    canvas = np.full(
        (header_h + tile_h + footer_h, tile_w * 4, 3),
        12,
        dtype=np.uint8,
    )
    canvas[header_h : header_h + tile_h] = np.concatenate(tiles, axis=1)

    for index, title in enumerate(labels):
        cv2.putText(
            canvas,
            title,
            (index * tile_w + 14, 29),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.56,
            (236, 236, 236),
            1,
            cv2.LINE_AA,
        )

    cv2.putText(
        canvas,
        f"{label} | locked-test MAE {mae:.2f}/255",
        (14, header_h + tile_h + 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (190, 190, 190),
        1,
        cv2.LINE_AA,
    )
    return canvas


def _aggregate(rows: list[dict]) -> dict:
    if not rows:
        return {"count": 0}

    def median(key: str) -> float:
        return float(np.median([float(row[key]) for row in rows]))

    def p90(key: str) -> float:
        return float(np.percentile([float(row[key]) for row in rows], 90))

    return {
        "count": len(rows),
        "median_no_edit_mae_255": median("no_edit_mae_255"),
        "median_mean_recipe_mae_255": median("mean_recipe_mae_255"),
        "median_candidate_mae_255": median("candidate_mae_255"),
        "p90_candidate_mae_255": p90("candidate_mae_255"),
        "median_candidate_psnr_db": median("candidate_psnr_db"),
        "median_improvement_vs_no_edit": median("improvement_vs_no_edit"),
        "median_improvement_vs_mean_recipe": median(
            "improvement_vs_mean_recipe"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a deliberate final audit of one frozen J1 candidate on locked "
            "Test events. Test images are never used to fit or update the model."
        )
    )
    parser.add_argument("--dataset-manifest", required=True)
    parser.add_argument("--candidate-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--unlock-test",
        action="store_true",
        help="Required explicit acknowledgement that locked Test will be opened.",
    )
    parser.add_argument("--jpeg-quality", type=int, default=95)
    args = parser.parse_args()

    if not args.unlock_test:
        raise ValueError(
            "Locked Test audit refused. Add --unlock-test only after the candidate "
            "is frozen and no more tuning decisions will use this Test set."
        )

    dataset_manifest_path = Path(args.dataset_manifest).expanduser().resolve(strict=True)
    candidate_dir = Path(args.candidate_dir).expanduser().resolve(strict=True)
    output = Path(args.output).expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(
            f"Audit output must be new/empty so results stay immutable: {output}"
        )
    output.mkdir(parents=True, exist_ok=True)

    dataset = _read_json(dataset_manifest_path)
    contract = _read_json(candidate_dir / "model" / "model_contract.json")
    candidate_summary = _read_json(candidate_dir / "summary.json")

    if dataset.get("kind") != "jpeg_real_event_dataset":
        raise ValueError("Unexpected dataset manifest kind.")

    snapshot_path = dataset.get("dataset_snapshot_path")
    snapshot_id = dataset.get("dataset_snapshot_id")
    if not snapshot_path or not snapshot_id:
        raise ValueError(
            "Dataset predates the frozen snapshot contract; locked Test is blocked."
        )
    load_and_validate_dataset_snapshot(
        snapshot_path,
        expected_snapshot_id=snapshot_id,
    )

    if contract.get("photographer_id") != dataset.get("photographer_id"):
        raise ValueError("Candidate and dataset photographer IDs do not match.")
    if contract.get("dataset_manifest_sha256") != _sha256_file(dataset_manifest_path):
        raise ValueError(
            "Frozen candidate was trained against a different dataset manifest."
        )
    if candidate_summary.get("candidate_id") != contract.get("candidate_id"):
        raise ValueError("Candidate summary/model contract mismatch.")
    if contract.get("feature_names") != list(FEATURE_NAMES):
        raise ValueError("Candidate feature contract is incompatible with this audit code.")
    if dataset.get("cross_split_duplicates"):
        raise ValueError("Cross-split duplicate leakage exists; Test audit is blocked.")

    test_pairs = [
        pair
        for pair in dataset.get("pairs", [])
        if pair.get("split") == "test" and pair.get("usable_for_recipe_fit")
    ]
    if not test_pairs:
        raise ValueError("No usable locked Test pairs are present in the dataset.")

    model = np.load(candidate_dir / "model" / "model.npz")
    weights = model["weights"]
    feature_mean = model["feature_mean"]
    feature_std = model["feature_std"]
    mean_recipe_delta = model["mean_recipe_delta"]

    prediction_dir = output / "predictions"
    baseline_dir = output / "mean_recipe"
    prediction_dir.mkdir(parents=True, exist_ok=True)
    baseline_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    contact_rows: list[np.ndarray] = []
    aspect_tolerance = float(dataset.get("aspect_tolerance", 0.01))
    jpeg_quality = min(100, max(50, int(args.jpeg_quality)))

    for pair in test_pairs:
        original_native = _read_image(Path(pair["original_path"]))
        photographer_native = _read_image(Path(pair["edited_path"]))
        aligned_original, photographer, geometry_action = _match_geometry(
            original_native,
            photographer_native,
            aspect_tolerance=aspect_tolerance,
        )

        features = extract_features(original_native)
        standardized = features.copy()
        standardized[1:] = (
            standardized[1:] - feature_mean
        ) / feature_std
        standardized[0] = 1.0

        predicted_delta = standardized @ weights
        predicted_recipe = _restore_recipe(predicted_delta)
        mean_recipe = _restore_recipe(mean_recipe_delta)

        prediction = _apply_recipe_uint8(aligned_original, predicted_recipe)
        mean_baseline = _apply_recipe_uint8(aligned_original, mean_recipe)

        no_edit_mae, _, _ = _image_metrics(aligned_original, photographer)
        mean_mae, _, _ = _image_metrics(mean_baseline, photographer)
        candidate_mae, candidate_rmse, candidate_psnr = _image_metrics(
            prediction,
            photographer,
        )

        pair_id = pair["pair_id"]
        prediction_path = prediction_dir / f"{pair_id}.jpg"
        baseline_path = baseline_dir / f"{pair_id}.jpg"
        _write_jpeg(prediction_path, prediction, quality=jpeg_quality)
        _write_jpeg(baseline_path, mean_baseline, quality=jpeg_quality)

        row = {
            "pair_id": pair_id,
            "event_id": pair["event_id"],
            "split": "test",
            "original_path": pair["original_path"],
            "edited_path": pair["edited_path"],
            "geometry_action": geometry_action,
            "prediction_path": str(prediction_path),
            "mean_recipe_path": str(baseline_path),
            "no_edit_mae_255": no_edit_mae,
            "mean_recipe_mae_255": mean_mae,
            "candidate_mae_255": candidate_mae,
            "candidate_rmse_255": candidate_rmse,
            "candidate_psnr_db": candidate_psnr,
            "improvement_vs_no_edit": (
                0.0
                if no_edit_mae <= 1e-12
                else 1.0 - candidate_mae / no_edit_mae
            ),
            "improvement_vs_mean_recipe": (
                0.0
                if mean_mae <= 1e-12
                else 1.0 - candidate_mae / mean_mae
            ),
        }
        rows.append(row)

        if len(contact_rows) < 12:
            contact_rows.append(
                _comparison_row(
                    aligned_original,
                    photographer,
                    prediction,
                    mean_baseline,
                    label=f"{pair['event_id']} / {Path(pair['original_path']).name}",
                    mae=candidate_mae,
                )
            )

    if contact_rows:
        _write_jpeg(
            output / "test_contact_sheet.jpg",
            np.concatenate(contact_rows, axis=0),
            quality=jpeg_quality,
        )

    aggregate = _aggregate(rows)
    test_event_ids = sorted({row["event_id"] for row in rows})
    event_aggregates = {
        event_id: _aggregate([row for row in rows if row["event_id"] == event_id])
        for event_id in test_event_ids
    }

    report = {
        "schema_version": SCHEMA_VERSION,
        "experiment": "JPEG Brain J1 — Locked Real Test Audit",
        "created_at": _utc_now(),
        "candidate_id": contract.get("candidate_id"),
        "candidate_dir": str(candidate_dir),
        "candidate_model_version": contract.get("model_version"),
        "photographer_id": dataset.get("photographer_id"),
        "dataset_manifest_path": str(dataset_manifest_path),
        "dataset_manifest_sha256": _sha256_file(dataset_manifest_path),
        "test_unlocked": True,
        "candidate_weights_modified": False,
        "test_used_for_training": False,
        "test_used_for_candidate_selection": False,
        "test_events": test_event_ids,
        "test_pair_count": len(rows),
        "aggregate": aggregate,
        "by_event": event_aggregates,
        "descriptive_comparisons": {
            "candidate_better_than_no_edit_median": (
                aggregate.get("median_candidate_mae_255", float("inf"))
                < aggregate.get("median_no_edit_mae_255", float("inf"))
            ),
            "candidate_better_than_mean_recipe_median": (
                aggregate.get("median_candidate_mae_255", float("inf"))
                < aggregate.get("median_mean_recipe_mae_255", float("inf"))
            ),
        },
        "interpretation": (
            "This is a one-way audit of a frozen candidate on locked Test events. "
            "The model is not refit or updated. The result is descriptive and must "
            "not be used to tune this same candidate against this Test set. Real "
            "product-quality and time-savings claims require representative material "
            "and human workflow evaluation."
        ),
    }

    _write_json(output / "test_audit.json", report)
    _write_csv(output / "test_results.csv", rows)

    print("=" * 80)
    print("JPEG Brain J1 — Locked Real Test Audit")
    print("=" * 80)
    print(f"Candidate ID:                    {contract.get('candidate_id')}")
    print(f"Test events:                     {len(test_event_ids)}")
    print(f"Test pairs:                      {len(rows)}")
    print()
    print(
        "Test median no-edit MAE:         "
        f"{aggregate.get('median_no_edit_mae_255', 0.0):.2f}/255"
    )
    print(
        "Test mean-recipe MAE:            "
        f"{aggregate.get('median_mean_recipe_mae_255', 0.0):.2f}/255"
    )
    print(
        "Test frozen-candidate MAE:       "
        f"{aggregate.get('median_candidate_mae_255', 0.0):.2f}/255"
    )
    print(
        "Test improvement/no-edit:        "
        f"{aggregate.get('median_improvement_vs_no_edit', 0.0) * 100.0:.1f}%"
    )
    print(
        "Test improvement/mean:           "
        f"{aggregate.get('median_improvement_vs_mean_recipe', 0.0) * 100.0:.1f}%"
    )
    print()
    print("Candidate weights modified:       NO")
    print("Test used for training:            NO")
    print(f"Audit output:                     {output}")
    print()
    print("Do not tune this frozen candidate against this Test result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
