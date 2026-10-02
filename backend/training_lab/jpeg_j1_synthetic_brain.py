from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

from jpeg_j0_feasibility import (
    FEATURE_NAMES as RECIPE_FEATURE_NAMES,
    _apply_recipe_uint8,
    _write_jpeg,
)


EXPERIMENT = "JPEG Brain J1 — Synthetic Recipe Prediction"
MODEL_VERSION = "jpeg-j1-measured-features-ridge-v1"
DATASET_VERSION = "jpeg-j1-synthetic-events-v1"

TRAIN_EVENTS = tuple(f"train-{i:02d}" for i in range(1, 9))
VALIDATION_EVENTS = ("validation-01", "validation-02")
TEST_EVENTS = ("test-01", "test-02")
ALL_EVENTS = TRAIN_EVENTS + VALIDATION_EVENTS + TEST_EVENTS

FEATURE_NAMES = (
    "bias",
    "mean_r",
    "mean_g",
    "mean_b",
    "std_r",
    "std_g",
    "std_b",
    "p10_luma",
    "p50_luma",
    "p90_luma",
    "luma_std",
    "mean_saturation",
    "p90_saturation",
    "highlight_fraction",
    "shadow_fraction",
    "warmth",
    "green_magenta",
)


@dataclass(frozen=True)
class SampleResult:
    event_id: str
    split: str
    sample_id: str
    original_path: str
    ground_truth_path: str
    prediction_path: str
    baseline_path: str
    no_edit_mae_255: float
    mean_recipe_mae_255: float
    j1_mae_255: float
    j1_rmse_255: float
    j1_psnr_db: float
    improvement_vs_no_edit: float
    improvement_vs_mean_recipe: float
    recipe_rmse: float


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _sha256_array(array: np.ndarray) -> str:
    return hashlib.sha256(array.tobytes()).hexdigest()


def _identity_recipe() -> np.ndarray:
    coefficients = np.zeros((len(RECIPE_FEATURE_NAMES), 3), dtype=np.float64)
    coefficients[1, 0] = 1.0
    coefficients[2, 1] = 1.0
    coefficients[3, 2] = 1.0
    return coefficients


IDENTITY_RECIPE = _identity_recipe()


def _make_scene(event_index: int, image_index: int, width: int, height: int) -> np.ndarray:
    seed = 100_000 + event_index * 10_000 + image_index
    rng = np.random.default_rng(seed)

    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    x = xx / max(width - 1, 1)
    y = yy / max(height - 1, 1)

    event_warmth = rng.normal(0.0, 0.055) + (event_index - 5.5) * 0.004
    event_brightness = rng.normal(0.0, 0.040)
    event_green = rng.normal(0.0, 0.025)

    r = 0.09 + 0.42 * x + 0.16 * (1.0 - y) + event_warmth + event_brightness
    g = 0.08 + 0.34 * x + 0.24 * y + event_green + event_brightness
    b = 0.12 + 0.24 * (1.0 - x) + 0.32 * y - event_warmth + event_brightness

    wave = 0.035 * np.sin((2.0 + 0.2 * event_index) * np.pi * x)
    wave += 0.025 * np.cos((2.0 + 0.1 * image_index) * np.pi * y)
    r += wave
    g += wave * 0.65
    b += wave * 0.35

    light_count = 7 + (image_index % 5)
    for _ in range(light_count):
        cx = rng.uniform(0.05, 0.95)
        cy = rng.uniform(0.06, 0.90)
        sigma_x = rng.uniform(0.018, 0.090)
        sigma_y = rng.uniform(0.018, 0.095)
        energy = rng.uniform(0.035, 0.19)
        blob = np.exp(
            -(
                ((x - cx) ** 2) / (2.0 * sigma_x * sigma_x)
                + ((y - cy) ** 2) / (2.0 * sigma_y * sigma_y)
            )
        )
        tint = rng.uniform(0.72, 1.28, size=3)
        r += blob * energy * tint[0]
        g += blob * energy * tint[1]
        b += blob * energy * tint[2]

    rgb = np.stack([r, g, b], axis=-1)
    rgb += rng.normal(0.0, 0.0075, size=rgb.shape).astype(np.float32)
    rgb = np.clip(rgb, 0.0, 1.0)
    image = np.rint(rgb * 255.0).astype(np.uint8)

    skin_center = (
        int(width * (0.22 + 0.055 * ((image_index + event_index) % 6))),
        int(height * (0.40 + 0.035 * (image_index % 4))),
    )
    skin_color = (
        int(np.clip(185 + event_warmth * 150, 130, 225)),
        int(np.clip(132 + event_green * 100, 95, 175)),
        int(np.clip(110 - event_warmth * 110, 80, 160)),
    )
    cv2.ellipse(
        image,
        skin_center,
        (int(width * 0.065), int(height * 0.12)),
        (event_index * 7 + image_index * 3) % 18 - 9,
        0,
        360,
        skin_color,
        -1,
    )

    cv2.rectangle(
        image,
        (int(width * 0.58), int(height * 0.54)),
        (int(width * 0.90), int(height * 0.84)),
        (
            int(np.clip(42 + 4 * event_index, 20, 100)),
            int(np.clip(72 + 2 * image_index, 45, 130)),
            int(np.clip(110 + 3 * event_index, 75, 170)),
        ),
        -1,
    )

    cv2.circle(
        image,
        (int(width * (0.73 + 0.02 * math.sin(image_index))), int(height * 0.25)),
        int(min(width, height) * (0.055 + 0.005 * (image_index % 4))),
        (224, 197, 148),
        -1,
    )

    return image


def _rgb_float(image: np.ndarray) -> np.ndarray:
    return image.astype(np.float32) / 255.0


def extract_features(image: np.ndarray) -> np.ndarray:
    rgb = _rgb_float(image).reshape(-1, 3)
    mean = rgb.mean(axis=0)
    std = rgb.std(axis=0)

    luma = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    p10_luma, p50_luma, p90_luma = np.percentile(luma, [10, 50, 90])
    luma_std = float(luma.std())

    channel_max = rgb.max(axis=1)
    channel_min = rgb.min(axis=1)
    saturation = (channel_max - channel_min) / np.maximum(channel_max, 1e-6)

    highlight_fraction = float(np.mean(channel_max >= 0.94))
    shadow_fraction = float(np.mean(luma <= 0.10))
    warmth = float(mean[0] - mean[2])
    green_magenta = float(mean[1] - 0.5 * (mean[0] + mean[2]))

    return np.asarray(
        (
            1.0,
            mean[0],
            mean[1],
            mean[2],
            std[0],
            std[1],
            std[2],
            p10_luma,
            p50_luma,
            p90_luma,
            luma_std,
            float(np.mean(saturation)),
            float(np.percentile(saturation, 90)),
            highlight_fraction,
            shadow_fraction,
            warmth,
            green_magenta,
        ),
        dtype=np.float64,
    )


def _ground_truth_recipe(features: np.ndarray) -> np.ndarray:
    f = dict(zip(FEATURE_NAMES, features.tolist()))
    c = IDENTITY_RECIPE.copy()

    under = np.clip(0.48 - f["p50_luma"], -0.22, 0.28)
    contrast_need = np.clip(0.21 - f["luma_std"], -0.12, 0.14)
    warm_need = np.clip(0.035 - f["warmth"], -0.16, 0.16)
    green_need = np.clip(-f["green_magenta"], -0.09, 0.09)
    saturation_need = np.clip(0.31 - f["mean_saturation"], -0.16, 0.20)
    highlight_pressure = np.clip(f["highlight_fraction"] - 0.025, -0.025, 0.16)
    shadow_pressure = np.clip(f["shadow_fraction"] - 0.08, -0.08, 0.22)

    base_lift = 0.12 * under + 0.035 * shadow_pressure
    c[0] += [
        base_lift + 0.055 * warm_need,
        base_lift + 0.028 * green_need,
        base_lift - 0.055 * warm_need,
    ]

    diagonal = 0.26 * under + 0.17 * contrast_need
    c[1, 0] += diagonal + 0.08 * warm_need
    c[2, 1] += diagonal + 0.06 * green_need
    c[3, 2] += diagonal - 0.08 * warm_need

    curve = 0.22 * contrast_need - 0.16 * highlight_pressure + 0.08 * shadow_pressure
    c[4, 0] += curve + 0.045 * warm_need
    c[5, 1] += curve * 0.92
    c[6, 2] += curve - 0.045 * warm_need

    cross = 0.055 * saturation_need
    c[7, 0] += cross + 0.022 * warm_need
    c[7, 1] -= cross * 0.45
    c[8, 0] += cross * 0.40
    c[8, 2] += cross + 0.018 * warm_need
    c[9, 1] += cross * 0.75 + 0.018 * green_need
    c[9, 2] += cross * 0.35

    return c


def _flatten_recipe_delta(recipe: np.ndarray) -> np.ndarray:
    return (recipe - IDENTITY_RECIPE).reshape(-1)


def _restore_recipe(delta: np.ndarray) -> np.ndarray:
    return IDENTITY_RECIPE + delta.reshape(IDENTITY_RECIPE.shape)


def _split_for_event(event_id: str) -> str:
    if event_id in TRAIN_EVENTS:
        return "train"
    if event_id in VALIDATION_EVENTS:
        return "validation"
    if event_id in TEST_EVENTS:
        return "test"
    raise KeyError(event_id)


def _ridge_fit(x: np.ndarray, y: np.ndarray, ridge_lambda: float) -> np.ndarray:
    regularizer = np.eye(x.shape[1], dtype=np.float64) * ridge_lambda
    regularizer[0, 0] = ridge_lambda * 0.1
    return np.linalg.solve(x.T @ x + regularizer, x.T @ y)


def _standardize_train(
    x_train: np.ndarray,
    x_other: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mean = x_train[:, 1:].mean(axis=0)
    std = x_train[:, 1:].std(axis=0)
    std = np.where(std < 1e-8, 1.0, std)

    def transform(x: np.ndarray) -> np.ndarray:
        result = x.copy()
        result[:, 1:] = (result[:, 1:] - mean) / std
        result[:, 0] = 1.0
        return result

    return transform(x_train), transform(x_other), mean, std


def _image_metrics(predicted: np.ndarray, target: np.ndarray) -> tuple[float, float, float]:
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
    ground_truth: np.ndarray,
    predicted: np.ndarray,
    baseline: np.ndarray,
    label: str,
    j1_mae: float,
) -> np.ndarray:
    tile_w = 320
    tile_h = 220
    header_h = 44
    footer_h = 32
    labels = ("ORIGINAL", "GROUND TRUTH", "J1 PREDICTION", "MEAN BASELINE")
    tiles = [
        _fit_tile(original, tile_w, tile_h),
        _fit_tile(ground_truth, tile_w, tile_h),
        _fit_tile(predicted, tile_w, tile_h),
        _fit_tile(baseline, tile_w, tile_h),
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
            0.60,
            (236, 236, 236),
            1,
            cv2.LINE_AA,
        )

    cv2.putText(
        canvas,
        f"{label} | J1 MAE {j1_mae:.2f}/255",
        (14, header_h + tile_h + 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.54,
        (190, 190, 190),
        1,
        cv2.LINE_AA,
    )
    return canvas


def _generate_dataset(
    root: Path,
    *,
    images_per_event: int,
    width: int,
    height: int,
    jpeg_quality: int,
) -> list[dict]:
    records: list[dict] = []
    originals_dir = root / "originals"
    targets_dir = root / "ground_truth"
    originals_dir.mkdir(parents=True, exist_ok=True)
    targets_dir.mkdir(parents=True, exist_ok=True)

    for event_index, event_id in enumerate(ALL_EVENTS):
        split = _split_for_event(event_id)
        for image_index in range(images_per_event):
            sample_id = f"{event_id}_{image_index + 1:03d}"
            generated_original = _make_scene(
                event_index=event_index,
                image_index=image_index,
                width=width,
                height=height,
            )

            original_path = originals_dir / event_id / f"{sample_id}.jpg"
            target_path = targets_dir / event_id / f"{sample_id}.jpg"
            _write_jpeg(original_path, generated_original, quality=jpeg_quality)

            # Re-read the persisted JPEG before feature extraction and target creation.
            # This keeps training and inference semantics tied to the actual JPEG bytes
            # instead of the pre-encoding synthetic RGB array.
            persisted_bgr = cv2.imread(str(original_path), cv2.IMREAD_COLOR)
            if persisted_bgr is None:
                raise RuntimeError(f"Could not decode generated original: {original_path}")
            original = cv2.cvtColor(persisted_bgr, cv2.COLOR_BGR2RGB)

            features = extract_features(original)
            recipe = _ground_truth_recipe(features)
            target = _apply_recipe_uint8(original, recipe)
            _write_jpeg(target_path, target, quality=jpeg_quality)

            records.append(
                {
                    "event_id": event_id,
                    "split": split,
                    "sample_id": sample_id,
                    "original_path": str(original_path.resolve()),
                    "ground_truth_path": str(target_path.resolve()),
                    "features": features.tolist(),
                    "recipe_delta": _flatten_recipe_delta(recipe).tolist(),
                    "original_sha256_pixels": _sha256_array(original),
                    "target_sha256_pixels": _sha256_array(target),
                }
            )

    _write_json(
        root / "dataset_manifest.json",
        {
            "schema_version": 1,
            "dataset_version": DATASET_VERSION,
            "images_per_event": images_per_event,
            "events": {
                "train": list(TRAIN_EVENTS),
                "validation": list(VALIDATION_EVENTS),
                "test": list(TEST_EVENTS),
            },
            "feature_names": list(FEATURE_NAMES),
            "recipe_feature_names": list(RECIPE_FEATURE_NAMES),
            "records": records,
            "note": (
                "Synthetic engineering data only. Splits are event-level and fixed. "
                "This dataset does not support claims about real photographer quality."
            ),
        },
    )
    return records


def _matrix(records: list[dict], split: str) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    selected = [record for record in records if record["split"] == split]
    x = np.asarray([record["features"] for record in selected], dtype=np.float64)
    y = np.asarray([record["recipe_delta"] for record in selected], dtype=np.float64)
    return x, y, selected


def _evaluate(
    records: list[dict],
    *,
    split: str,
    feature_mean: np.ndarray,
    feature_std: np.ndarray,
    weights: np.ndarray,
    mean_recipe_delta: np.ndarray,
    output_root: Path,
    contact_limit: int,
    jpeg_quality: int,
) -> tuple[list[SampleResult], np.ndarray | None]:
    selected = [record for record in records if record["split"] == split]
    results: list[SampleResult] = []
    contact_rows: list[np.ndarray] = []

    pred_dir = output_root / split / "predictions"
    baseline_dir = output_root / split / "mean_baseline"
    pred_dir.mkdir(parents=True, exist_ok=True)
    baseline_dir.mkdir(parents=True, exist_ok=True)

    for index, record in enumerate(selected):
        original_bgr = cv2.imread(record["original_path"], cv2.IMREAD_COLOR)
        target_bgr = cv2.imread(record["ground_truth_path"], cv2.IMREAD_COLOR)
        if original_bgr is None or target_bgr is None:
            raise RuntimeError(f"Could not decode generated JPEG for {record['sample_id']}")
        original = cv2.cvtColor(original_bgr, cv2.COLOR_BGR2RGB)
        target = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2RGB)

        raw_features = np.asarray(record["features"], dtype=np.float64)
        standardized = raw_features.copy()
        standardized[1:] = (standardized[1:] - feature_mean) / feature_std
        standardized[0] = 1.0

        predicted_delta = standardized @ weights
        predicted_recipe = _restore_recipe(predicted_delta)
        mean_recipe = _restore_recipe(mean_recipe_delta)

        predicted = _apply_recipe_uint8(original, predicted_recipe)
        baseline = _apply_recipe_uint8(original, mean_recipe)

        no_edit_mae, _, _ = _image_metrics(original, target)
        baseline_mae, _, _ = _image_metrics(baseline, target)
        j1_mae, j1_rmse, j1_psnr = _image_metrics(predicted, target)

        prediction_path = pred_dir / f"{record['sample_id']}_j1.jpg"
        baseline_path = baseline_dir / f"{record['sample_id']}_mean.jpg"
        _write_jpeg(prediction_path, predicted, quality=jpeg_quality)
        _write_jpeg(baseline_path, baseline, quality=jpeg_quality)

        true_delta = np.asarray(record["recipe_delta"], dtype=np.float64)
        recipe_rmse = float(np.sqrt(np.mean(np.square(predicted_delta - true_delta))))

        result = SampleResult(
            event_id=record["event_id"],
            split=split,
            sample_id=record["sample_id"],
            original_path=record["original_path"],
            ground_truth_path=record["ground_truth_path"],
            prediction_path=str(prediction_path),
            baseline_path=str(baseline_path),
            no_edit_mae_255=no_edit_mae,
            mean_recipe_mae_255=baseline_mae,
            j1_mae_255=j1_mae,
            j1_rmse_255=j1_rmse,
            j1_psnr_db=j1_psnr,
            improvement_vs_no_edit=(
                0.0 if no_edit_mae <= 1e-12 else 1.0 - j1_mae / no_edit_mae
            ),
            improvement_vs_mean_recipe=(
                0.0 if baseline_mae <= 1e-12 else 1.0 - j1_mae / baseline_mae
            ),
            recipe_rmse=recipe_rmse,
        )
        results.append(result)

        if len(contact_rows) < contact_limit:
            contact_rows.append(
                _comparison_row(
                    original,
                    target,
                    predicted,
                    baseline,
                    label=record["sample_id"],
                    j1_mae=j1_mae,
                )
            )

    contact_sheet = np.concatenate(contact_rows, axis=0) if contact_rows else None
    return results, contact_sheet


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.median(np.asarray(values, dtype=np.float64)))


def _p90(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=np.float64), 90))


def _aggregate(results: list[SampleResult]) -> dict:
    return {
        "count": len(results),
        "median_no_edit_mae_255": _median([r.no_edit_mae_255 for r in results]),
        "median_mean_recipe_mae_255": _median(
            [r.mean_recipe_mae_255 for r in results]
        ),
        "median_j1_mae_255": _median([r.j1_mae_255 for r in results]),
        "p90_j1_mae_255": _p90([r.j1_mae_255 for r in results]),
        "median_j1_psnr_db": _median([r.j1_psnr_db for r in results]),
        "median_improvement_vs_no_edit": _median(
            [r.improvement_vs_no_edit for r in results]
        ),
        "median_improvement_vs_mean_recipe": _median(
            [r.improvement_vs_mean_recipe for r in results]
        ),
        "median_recipe_rmse": _median([r.recipe_rmse for r in results]),
    }


def _write_results_csv(path: Path, rows: list[SampleResult]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Train a small deterministic synthetic JPEG Brain J1 that predicts "
            "J0 recipe coefficients from measured image features, using fixed "
            "event-level train/validation/test splits."
        )
    )
    parser.add_argument("--output", required=True, help="Destination experiment folder")
    parser.add_argument("--clean", action="store_true", help="Delete output first")
    parser.add_argument(
        "--images-per-event",
        type=int,
        default=18,
        help="Synthetic images per event (default: 18)",
    )
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=426)
    parser.add_argument(
        "--ridge-lambda",
        type=float,
        default=0.02,
        help="Ridge regularization (default: 0.02)",
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=98,
        help="Synthetic dataset JPEG quality (default: 98)",
    )
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    if args.clean and output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    dataset_root = output / "dataset"
    records = _generate_dataset(
        dataset_root,
        images_per_event=max(6, args.images_per_event),
        width=max(320, args.width),
        height=max(220, args.height),
        jpeg_quality=min(100, max(90, args.jpeg_quality)),
    )

    x_train, y_train, _ = _matrix(records, "train")
    x_validation, _, _ = _matrix(records, "validation")
    x_test, _, _ = _matrix(records, "test")

    x_train_std, x_validation_std, feature_mean, feature_std = _standardize_train(
        x_train,
        x_validation,
    )
    x_train_std_again, x_test_std, feature_mean_test, feature_std_test = _standardize_train(
        x_train,
        x_test,
    )
    if not np.allclose(x_train_std, x_train_std_again):
        raise RuntimeError("feature standardization is not deterministic")
    if not np.allclose(feature_mean, feature_mean_test):
        raise RuntimeError("feature mean changed across transforms")
    if not np.allclose(feature_std, feature_std_test):
        raise RuntimeError("feature std changed across transforms")

    ridge_lambda = max(0.0, float(args.ridge_lambda))
    weights = _ridge_fit(x_train_std, y_train, ridge_lambda)
    mean_recipe_delta = y_train.mean(axis=0)

    model_dir = output / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        model_dir / "j1_model.npz",
        weights=weights,
        feature_mean=feature_mean,
        feature_std=feature_std,
        mean_recipe_delta=mean_recipe_delta,
    )
    _write_json(
        model_dir / "model_contract.json",
        {
            "schema_version": 1,
            "model_version": MODEL_VERSION,
            "dataset_version": DATASET_VERSION,
            "production_ready": False,
            "quality_claim_allowed": False,
            "input_feature_names": list(FEATURE_NAMES),
            "output_shape": list(IDENTITY_RECIPE.shape),
            "output_semantics": "delta_from_identity_quadratic_rgb_recipe",
            "recipe_feature_names": list(RECIPE_FEATURE_NAMES),
            "ridge_lambda": ridge_lambda,
            "train_events": list(TRAIN_EVENTS),
            "validation_events": list(VALIDATION_EVENTS),
            "test_events": list(TEST_EVENTS),
        },
    )

    validation_results, validation_contact = _evaluate(
        records,
        split="validation",
        feature_mean=feature_mean,
        feature_std=feature_std,
        weights=weights,
        mean_recipe_delta=mean_recipe_delta,
        output_root=output,
        contact_limit=8,
        jpeg_quality=95,
    )
    test_results, test_contact = _evaluate(
        records,
        split="test",
        feature_mean=feature_mean,
        feature_std=feature_std,
        weights=weights,
        mean_recipe_delta=mean_recipe_delta,
        output_root=output,
        contact_limit=8,
        jpeg_quality=95,
    )

    if validation_contact is not None:
        _write_jpeg(output / "validation_contact_sheet.jpg", validation_contact, quality=95)
    if test_contact is not None:
        _write_jpeg(output / "test_contact_sheet.jpg", test_contact, quality=95)

    _write_results_csv(output / "validation_results.csv", validation_results)
    _write_results_csv(output / "test_results.csv", test_results)

    validation_aggregate = _aggregate(validation_results)
    test_aggregate = _aggregate(test_results)

    validation_pass = bool(
        validation_aggregate["median_j1_mae_255"] is not None
        and validation_aggregate["median_mean_recipe_mae_255"] is not None
        and validation_aggregate["median_j1_mae_255"]
        < validation_aggregate["median_mean_recipe_mae_255"] * 0.65
        and validation_aggregate["median_improvement_vs_no_edit"] is not None
        and validation_aggregate["median_improvement_vs_no_edit"] >= 0.75
    )
    test_pass = bool(
        test_aggregate["median_j1_mae_255"] is not None
        and test_aggregate["median_mean_recipe_mae_255"] is not None
        and test_aggregate["median_j1_mae_255"]
        < test_aggregate["median_mean_recipe_mae_255"] * 0.70
        and test_aggregate["median_improvement_vs_no_edit"] is not None
        and test_aggregate["median_improvement_vs_no_edit"] >= 0.70
    )

    summary = {
        "schema_version": 1,
        "experiment": EXPERIMENT,
        "model_version": MODEL_VERSION,
        "dataset_version": DATASET_VERSION,
        "production_ready": False,
        "trained_model": True,
        "quality_claim_allowed": False,
        "synthetic_only": True,
        "events": {
            "train": list(TRAIN_EVENTS),
            "validation": list(VALIDATION_EVENTS),
            "test": list(TEST_EVENTS),
        },
        "sample_counts": {
            "train": int(len(x_train)),
            "validation": int(len(x_validation_std)),
            "test": int(len(x_test_std)),
        },
        "validation": validation_aggregate,
        "test": test_aggregate,
        "gates": {
            "validation_pass": validation_pass,
            "test_pass": test_pass,
            "overall_pass": validation_pass and test_pass,
            "validation_rule": (
                "median J1 MAE < 65% of mean-recipe baseline and >=75% median "
                "improvement over no-edit"
            ),
            "test_rule": (
                "median J1 MAE < 70% of mean-recipe baseline and >=70% median "
                "improvement over no-edit"
            ),
        },
        "interpretation": (
            "This experiment validates only that the Brain V2 learning pipeline can "
            "learn a known synthetic mapping from measured JPEG features to a compact "
            "J0 recipe and generalize to entirely held-out synthetic events. It is "
            "not evidence of real photographer-style quality."
        ),
    }
    _write_json(output / "summary.json", summary)

    print("=" * 80)
    print(EXPERIMENT)
    print("=" * 80)
    print(f"Train events:                    {len(TRAIN_EVENTS)}")
    print(f"Validation events:               {len(VALIDATION_EVENTS)}")
    print(f"Test events:                     {len(TEST_EVENTS)}")
    print(f"Train samples:                   {len(x_train)}")
    print(f"Validation samples:              {len(validation_results)}")
    print(f"Test samples:                    {len(test_results)}")
    print()
    print(
        "Validation median no-edit MAE:   "
        f"{validation_aggregate['median_no_edit_mae_255'] or 0.0:.2f}/255"
    )
    print(
        "Validation mean-recipe MAE:      "
        f"{validation_aggregate['median_mean_recipe_mae_255'] or 0.0:.2f}/255"
    )
    print(
        "Validation J1 MAE:               "
        f"{validation_aggregate['median_j1_mae_255'] or 0.0:.2f}/255"
    )
    print(
        "Validation improvement/no-edit:  "
        f"{(validation_aggregate['median_improvement_vs_no_edit'] or 0.0) * 100.0:.1f}%"
    )
    print()
    print(
        "Test median no-edit MAE:         "
        f"{test_aggregate['median_no_edit_mae_255'] or 0.0:.2f}/255"
    )
    print(
        "Test mean-recipe MAE:            "
        f"{test_aggregate['median_mean_recipe_mae_255'] or 0.0:.2f}/255"
    )
    print(
        "Test J1 MAE:                     "
        f"{test_aggregate['median_j1_mae_255'] or 0.0:.2f}/255"
    )
    print(
        "Test improvement/no-edit:        "
        f"{(test_aggregate['median_improvement_vs_no_edit'] or 0.0) * 100.0:.1f}%"
    )
    print()
    print(
        "Validation gate:                 "
        + ("PASS" if validation_pass else "FAIL")
    )
    print("Locked synthetic test gate:       " + ("PASS" if test_pass else "FAIL"))
    print(
        "J1 synthetic learning pipeline:  "
        + ("PASS" if validation_pass and test_pass else "FAIL")
    )
    print(f"Output:                           {output}")
    print()
    print("Inspect test_contact_sheet.jpg.")
    print(
        "The Test events were never used to fit the model or choose its weights. "
        "Synthetic PASS is not a photographer-quality claim."
    )

    return 0 if validation_pass and test_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
