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

from app.datasets.jpeg_integrity import (
    JPEG_COLOR_CONTRACT_VERSION,
    load_and_validate_dataset_snapshot,
)
from app.evaluation.artifact_provenance import (
    FEATURE_CONTRACT_VERSION,
    RENDERER_CONTRACT_VERSION,
    build_file_manifest,
    candidate_provenance,
    dependency_lock_fingerprint,
    ensure_immutable_artifact_dir,
    resolve_code_revision,
    sha256_file,
    verify_target_bundle_for_candidate,
    write_immutable_json,
)
from jpeg_j0_feasibility import (
    RECIPE_VERSION,
    _apply_recipe_uint8,
    _match_geometry,
    _read_image,
    _write_jpeg,
)
from jpeg_j1_synthetic_brain import (
    FEATURE_NAMES,
    IDENTITY_RECIPE,
    MODEL_VERSION as SYNTHETIC_MODEL_FAMILY,
    _ridge_fit,
    _restore_recipe,
    extract_features,
)


SCHEMA_VERSION = 1
MODEL_VERSION = "jpeg-j1-real-measured-features-ridge-v1"


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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _decode_rgb(path: str) -> np.ndarray:
    return _read_image(Path(path))


def _standardize_train(
    x_train: np.ndarray,
    x_other: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mean = x_train[:, 1:].mean(axis=0)
    std = x_train[:, 1:].std(axis=0)
    std = np.where(std < 1e-8, 1.0, std)

    train = x_train.copy()
    other = x_other.copy()
    train[:, 1:] = (train[:, 1:] - mean) / std
    other[:, 1:] = (other[:, 1:] - mean) / std
    train[:, 0] = 1.0
    other[:, 0] = 1.0
    return train, other, mean, std


def _recipe_delta(transform: dict) -> np.ndarray:
    coefficients = np.asarray(transform.get("coefficients"), dtype=np.float64)
    if coefficients.shape != IDENTITY_RECIPE.shape:
        raise ValueError(
            "Unexpected J0 recipe coefficient shape: "
            f"{coefficients.shape}; expected {IDENTITY_RECIPE.shape}"
        )
    return (coefficients - IDENTITY_RECIPE).reshape(-1)


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
    labels = ("ORIGINAL", "PHOTOGRAPHER", "J1 CANDIDATE", "MEAN RECIPE")
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
            0.58,
            (236, 236, 236),
            1,
            cv2.LINE_AA,
        )

    cv2.putText(
        canvas,
        f"{label} | candidate MAE {mae:.2f}/255",
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
        "median_recipe_rmse_vs_j0_target": median(
            "recipe_rmse_vs_j0_target"
        ),
    }


def _build_training_rows(dataset: dict, targets: dict) -> list[dict]:
    dataset_pairs = {
        pair["pair_id"]: pair
        for pair in dataset.get("pairs", [])
        if pair.get("usable_for_recipe_fit")
    }

    rows: list[dict] = []
    for target in targets.get("targets", []):
        pair_id = target.get("pair_id")
        pair = dataset_pairs.get(pair_id)
        if pair is None:
            raise ValueError(
                f"Recipe target {pair_id!r} is not present in the frozen dataset manifest."
            )

        split = target.get("split")
        if split == "test":
            raise ValueError(
                "recipe_targets.json contains locked Test targets. J1 Candidate training "
                "accepts Train/Validation targets only."
            )
        if split not in {"train", "validation"}:
            raise ValueError(f"Unsupported target split: {split!r}")
        if pair.get("split") != split:
            raise ValueError(
                f"Split mismatch for pair {pair_id}: dataset={pair.get('split')} target={split}"
            )
        if pair.get("original_sha256") != target.get("original_sha256"):
            raise ValueError(f"Original SHA-256 mismatch for pair {pair_id}")
        if pair.get("edited_sha256") != target.get("edited_sha256"):
            raise ValueError(f"Edited SHA-256 mismatch for pair {pair_id}")

        original = _decode_rgb(pair["original_path"])
        features = extract_features(original)
        delta = _recipe_delta(target["recipe_transform"])
        rows.append(
            {
                "pair": pair,
                "target": target,
                "split": split,
                "features": features,
                "recipe_delta": delta,
            }
        )

    return rows


def _evaluate_validation(
    rows: list[dict],
    *,
    feature_mean: np.ndarray,
    feature_std: np.ndarray,
    weights: np.ndarray,
    mean_recipe_delta: np.ndarray,
    output_dir: Path,
    aspect_tolerance: float,
    jpeg_quality: int,
) -> tuple[list[dict], np.ndarray | None]:
    results: list[dict] = []
    contact_rows: list[np.ndarray] = []

    predictions = output_dir / "validation" / "predictions"
    baselines = output_dir / "validation" / "mean_recipe"
    predictions.mkdir(parents=True, exist_ok=True)
    baselines.mkdir(parents=True, exist_ok=True)

    for row in rows:
        pair = row["pair"]
        original_native = _read_image(Path(pair["original_path"]))
        photographer_native = _read_image(Path(pair["edited_path"]))
        aligned_original, photographer, geometry_action = _match_geometry(
            original_native,
            photographer_native,
            aspect_tolerance=aspect_tolerance,
        )

        raw_features = row["features"].copy()
        standardized = raw_features.copy()
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

        true_delta = row["recipe_delta"]
        recipe_rmse = float(
            np.sqrt(np.mean(np.square(predicted_delta - true_delta)))
        )

        pair_id = pair["pair_id"]
        prediction_path = predictions / f"{pair_id}.jpg"
        baseline_path = baselines / f"{pair_id}.jpg"
        _write_jpeg(prediction_path, prediction, quality=jpeg_quality)
        _write_jpeg(baseline_path, mean_baseline, quality=jpeg_quality)

        result = {
            "pair_id": pair_id,
            "event_id": pair["event_id"],
            "split": "validation",
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
            "recipe_rmse_vs_j0_target": recipe_rmse,
        }
        results.append(result)

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

    contact_sheet = np.concatenate(contact_rows, axis=0) if contact_rows else None
    return results, contact_sheet


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Train the first real-JPEG J1 Candidate from frozen Train J0 recipe "
            "targets and evaluate it only on frozen Validation events."
        )
    )
    parser.add_argument("--dataset-manifest", required=True)
    parser.add_argument("--recipe-targets", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--ridge-lambda", type=float, default=0.02)
    parser.add_argument("--jpeg-quality", type=int, default=95)
    parser.add_argument(
        "--code-revision",
        help=(
            "Exact 40-character Git commit SHA. Defaults to git rev-parse HEAD "
            "or PROGRAPHER_CODE_REVISION."
        ),
    )
    args = parser.parse_args()

    dataset_manifest_path = Path(args.dataset_manifest).expanduser().resolve(strict=True)
    recipe_targets_path = Path(args.recipe_targets).expanduser().resolve(strict=True)
    output_root = Path(args.output).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    dataset = _read_json(dataset_manifest_path)
    targets = _read_json(recipe_targets_path)

    if dataset.get("kind") != "jpeg_real_event_dataset":
        raise ValueError("Unexpected dataset manifest kind.")

    snapshot_path = dataset.get("dataset_snapshot_path")
    snapshot_id = dataset.get("dataset_snapshot_id")
    if not snapshot_path or not snapshot_id:
        raise ValueError(
            "Dataset predates the frozen snapshot contract; re-run intake before J1."
        )
    load_and_validate_dataset_snapshot(
        snapshot_path,
        expected_snapshot_id=snapshot_id,
    )

    if targets.get("kind") != "jpeg_j0_recipe_targets":
        raise ValueError("Unexpected recipe target kind.")
    if dataset.get("photographer_id") != targets.get("photographer_id"):
        raise ValueError("Photographer id mismatch between dataset and J0 targets.")
    if dataset.get("cross_split_duplicates"):
        raise ValueError("Cross-split duplicate leakage exists; candidate training is blocked.")
    if dataset.get("cross_split_source_groups"):
        raise ValueError("Source-group split leakage exists; candidate training is blocked.")
    if dataset.get("unresolved_near_duplicate_suspects"):
        raise ValueError(
            "Unresolved near-duplicate suspects exist; candidate training is blocked."
        )
    if not dataset.get("readiness", {}).get(
        "whole_event_train_validation_test_ready"
    ):
        raise ValueError(
            "Dataset is not ready for whole-event Train/Validation/Test evaluation."
        )

    dataset_manifest_sha256 = sha256_file(dataset_manifest_path)
    target_provenance = verify_target_bundle_for_candidate(
        target_payload=targets,
        dataset_snapshot_id=str(snapshot_id),
        dataset_manifest_sha256=dataset_manifest_sha256,
    )

    rows = _build_training_rows(dataset, targets)
    train_rows = [row for row in rows if row["split"] == "train"]
    validation_rows = [row for row in rows if row["split"] == "validation"]
    if not train_rows:
        raise ValueError("No Train recipe targets are available.")
    if not validation_rows:
        raise ValueError("No Validation recipe targets are available.")

    x_train = np.asarray([row["features"] for row in train_rows], dtype=np.float64)
    y_train = np.asarray(
        [row["recipe_delta"] for row in train_rows],
        dtype=np.float64,
    )
    x_validation = np.asarray(
        [row["features"] for row in validation_rows],
        dtype=np.float64,
    )

    x_train_std, _, feature_mean, feature_std = _standardize_train(
        x_train,
        x_validation,
    )
    ridge_lambda = max(0.0, float(args.ridge_lambda))
    weights = _ridge_fit(x_train_std, y_train, ridge_lambda)
    mean_recipe_delta = y_train.mean(axis=0)

    resolved_revision = resolve_code_revision(args.code_revision)
    dependency = dependency_lock_fingerprint()
    jpeg_quality = min(100, max(50, int(args.jpeg_quality)))
    candidate_config = {
        "ridge_lambda": ridge_lambda,
        "jpeg_quality": jpeg_quality,
        "standardization": "train-zscore-except-bias-v1",
        "estimator": "closed-form-ridge-v1",
    }
    provenance = candidate_provenance(
        candidate_family="measured_features_ridge",
        model_version=MODEL_VERSION,
        dataset_snapshot_id=str(snapshot_id),
        dataset_manifest_sha256=dataset_manifest_sha256,
        target_artifact_id=target_provenance["artifact_id"],
        target_semantics_sha256_value=target_provenance["identity"][
            "target_semantics_sha256"
        ],
        target_artifact_sha256=sha256_file(recipe_targets_path),
        code_revision=resolved_revision,
        dependency_lock_sha256=dependency["dependency_lock_sha256"],
        color_contract_version=str(
            dataset.get("color_contract_version")
            or JPEG_COLOR_CONTRACT_VERSION
        ),
        feature_contract_version=FEATURE_CONTRACT_VERSION,
        feature_names=list(FEATURE_NAMES),
        recipe_contract_version=RECIPE_VERSION,
        renderer_contract_version=RENDERER_CONTRACT_VERSION,
        config=candidate_config,
    )
    candidate_id = provenance["artifact_id"]
    candidate_dir = ensure_immutable_artifact_dir(
        output_root / "candidates",
        candidate_id,
    )
    write_immutable_json(
        candidate_dir / "candidate_provenance.json",
        provenance,
    )

    model_dir = candidate_dir / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        model_dir / "model.npz",
        weights=weights,
        feature_mean=feature_mean,
        feature_std=feature_std,
        mean_recipe_delta=mean_recipe_delta,
    )

    training_event_ids = sorted(
        {row["pair"]["event_id"] for row in train_rows}
    )
    validation_event_ids = sorted(
        {row["pair"]["event_id"] for row in validation_rows}
    )
    test_event_ids = sorted(
        event["event_id"]
        for event in dataset.get("events", [])
        if event.get("split") == "test"
    )

    _write_json(
        model_dir / "model_contract.json",
        {
            "schema_version": SCHEMA_VERSION,
            "candidate_id": candidate_id,
            "model_version": MODEL_VERSION,
            "provenance": provenance,
            "code_revision": resolved_revision,
            "dependency_lock_name": dependency["dependency_lock_name"],
            "dependency_lock_sha256": dependency["dependency_lock_sha256"],
            "color_contract_version": provenance["identity"]["color_contract_version"],
            "feature_contract_version": FEATURE_CONTRACT_VERSION,
            "recipe_contract_version": RECIPE_VERSION,
            "renderer_contract_version": RENDERER_CONTRACT_VERSION,
            "target_artifact_id": target_provenance["artifact_id"],
            "synthetic_predecessor_family": SYNTHETIC_MODEL_FAMILY,
            "created_at": _utc_now(),
            "production_ready": False,
            "quality_claim_allowed": False,
            "photographer_id": dataset.get("photographer_id"),
            "feature_names": list(FEATURE_NAMES),
            "recipe_shape": list(IDENTITY_RECIPE.shape),
            "recipe_semantics": "delta_from_identity_quadratic_rgb_recipe",
            "ridge_lambda": ridge_lambda,
            "train_events": training_event_ids,
            "validation_events": validation_event_ids,
            "locked_test_events": test_event_ids,
            "train_pair_count": len(train_rows),
            "validation_pair_count": len(validation_rows),
            "dataset_snapshot_id": snapshot_id,
            "dataset_manifest_sha256": dataset_manifest_sha256,
            "recipe_targets_sha256": sha256_file(recipe_targets_path),
            "note": (
                "This candidate was fit only on Train recipe targets. Validation was "
                "not used to fit model weights. Locked Test remains untouched."
            ),
        },
    )

    validation_results, contact_sheet = _evaluate_validation(
        validation_rows,
        feature_mean=feature_mean,
        feature_std=feature_std,
        weights=weights,
        mean_recipe_delta=mean_recipe_delta,
        output_dir=candidate_dir,
        aspect_tolerance=float(dataset.get("aspect_tolerance", 0.01)),
        jpeg_quality=jpeg_quality,
    )
    if contact_sheet is not None:
        _write_jpeg(
            candidate_dir / "validation_contact_sheet.jpg",
            contact_sheet,
            quality=min(100, max(50, int(args.jpeg_quality))),
        )

    aggregate = _aggregate(validation_results)
    event_aggregates = {
        event_id: _aggregate(
            [row for row in validation_results if row["event_id"] == event_id]
        )
        for event_id in validation_event_ids
    }

    warnings: list[str] = []
    if len(train_rows) < len(FEATURE_NAMES):
        warnings.append(
            "Train pair count is smaller than the measured-feature count. Ridge can "
            "fit a plumbing candidate, but this sample is too small for a substantive "
            "real-photographer learning conclusion."
        )
    if len(training_event_ids) < 3:
        warnings.append(
            "Fewer than 3 Train events are available. Treat results as limited."
        )
    if len(validation_event_ids) < 2:
        warnings.append(
            "Only one Validation event is available. Event-level generalization evidence "
            "is limited until more independent events arrive."
        )

    summary = {
        "schema_version": SCHEMA_VERSION,
        "experiment": "JPEG Brain J1 — Real Candidate",
        "candidate_id": candidate_id,
        "model_version": MODEL_VERSION,
        "provenance": provenance,
        "candidate_lifecycle": {
            "state": "evaluated_validation",
            "promotion_status": "not_promoted",
            "immutable": True,
        },
        "created_at": _utc_now(),
        "production_ready": False,
        "quality_claim_allowed": False,
        "photographer_id": dataset.get("photographer_id"),
        "train": {
            "events": training_event_ids,
            "pair_count": len(train_rows),
        },
        "validation": {
            "events": validation_event_ids,
            "pair_count": len(validation_rows),
            "aggregate": aggregate,
            "by_event": event_aggregates,
        },
        "locked_test": {
            "events": test_event_ids,
            "opened": False,
            "evaluated": False,
        },
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
        "warnings": warnings,
        "interpretation": (
            "This is the first real-material candidate path. It trains only on Train "
            "J0 recipe targets and evaluates on held-out Validation events. Validation "
            "results guide candidate development; they are not a final Test audit and "
            "do not justify a product quality or time-savings claim."
        ),
    }
    _write_json(candidate_dir / "summary.json", summary)
    _write_csv(candidate_dir / "validation_results.csv", validation_results)

    manifest_files = [
        "candidate_provenance.json",
        "model/model.npz",
        "model/model_contract.json",
        "summary.json",
        "validation_results.csv",
    ]
    if (candidate_dir / "validation_contact_sheet.jpg").is_file():
        manifest_files.append("validation_contact_sheet.jpg")

    artifact_manifest = build_file_manifest(
        candidate_dir,
        manifest_files,
        candidate_id=candidate_id,
    )
    write_immutable_json(
        candidate_dir / "artifact_manifest.json",
        artifact_manifest,
    )

    _write_json(
        output_root / "latest_candidate.json",
        {
            "candidate_id": candidate_id,
            "candidate_dir": str(candidate_dir),
            "created_at": summary["created_at"],
            "code_revision": resolved_revision,
            "dataset_snapshot_id": snapshot_id,
            "target_artifact_id": target_provenance["artifact_id"],
            "artifact_manifest_path": str(candidate_dir / "artifact_manifest.json"),
            "artifact_manifest_sha256": sha256_file(
                candidate_dir / "artifact_manifest.json"
            ),
            "note": "Mutable pointer only. Candidate artifacts themselves are immutable.",
        },
    )

    print("=" * 80)
    print("JPEG Brain J1 — Real Candidate")
    print("=" * 80)
    print(f"Candidate ID:                    {candidate_id}")
    print(f"Train events:                    {len(training_event_ids)}")
    print(f"Train pairs:                     {len(train_rows)}")
    print(f"Validation events:               {len(validation_event_ids)}")
    print(f"Validation pairs:                {len(validation_rows)}")
    print(f"Locked Test events:              {len(test_event_ids)}")
    print()
    print(
        "Validation median no-edit MAE:   "
        f"{aggregate.get('median_no_edit_mae_255', 0.0):.2f}/255"
    )
    print(
        "Validation mean-recipe MAE:      "
        f"{aggregate.get('median_mean_recipe_mae_255', 0.0):.2f}/255"
    )
    print(
        "Validation J1 candidate MAE:     "
        f"{aggregate.get('median_candidate_mae_255', 0.0):.2f}/255"
    )
    print(
        "Validation improvement/no-edit:  "
        f"{aggregate.get('median_improvement_vs_no_edit', 0.0) * 100.0:.1f}%"
    )
    print(
        "Validation improvement/mean:     "
        f"{aggregate.get('median_improvement_vs_mean_recipe', 0.0) * 100.0:.1f}%"
    )
    print()
    print("Locked Test opened:              NO")
    print(f"Candidate output:                {candidate_dir}")
    if warnings:
        print()
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    print()
    print("Inspect validation_contact_sheet.jpg.")
    print(
        "This run does not promote the candidate and does not make a photographer-quality claim."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
