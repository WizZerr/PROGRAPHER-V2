from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.datasets.jpeg_integrity import read_jpeg_working_rgb


RECIPE_VERSION = "jpeg-recipe-j0-polynomial-v1"
FEATURE_NAMES = (
    "bias",
    "r",
    "g",
    "b",
    "r2",
    "g2",
    "b2",
    "rg",
    "rb",
    "gb",
)


@dataclass(frozen=True)
class PairMetrics:
    index: int
    original_path: str
    edited_path: str
    geometry_action: str
    baseline_mae_255: float
    reconstruction_mae_255: float
    reconstruction_rmse_255: float
    reconstruction_p95_abs_255: float
    reconstruction_luma_mae_255: float
    reconstruction_psnr_db: float
    mae_improvement_fraction: float
    recipe_path: str
    comparison_path: str


@dataclass(frozen=True)
class SkippedPair:
    index: int
    original_path: str
    edited_path: str
    reason: str


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


def _read_image(path: Path) -> np.ndarray:
    image, _ = read_jpeg_working_rgb(path)
    return image


def _write_jpeg(path: Path, rgb: np.ndarray, quality: int = 95) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    ok, encoded = cv2.imencode(
        ".jpg",
        bgr,
        [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)],
    )
    if not ok:
        raise RuntimeError(f"Could not encode JPEG: {path}")
    path.write_bytes(encoded.tobytes())


def _resize_max_edge(image: np.ndarray, max_edge: int) -> np.ndarray:
    height, width = image.shape[:2]
    largest = max(height, width)
    if largest <= max_edge:
        return image
    scale = max_edge / float(largest)
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return cv2.resize(image, size, interpolation=cv2.INTER_AREA)


def _match_geometry(
    original: np.ndarray,
    edited: np.ndarray,
    *,
    aspect_tolerance: float,
) -> tuple[np.ndarray, np.ndarray, str]:
    oh, ow = original.shape[:2]
    eh, ew = edited.shape[:2]

    if (oh, ow) == (eh, ew):
        return original, edited, "same_dimensions"

    original_ratio = ow / float(oh)
    edited_ratio = ew / float(eh)
    relative_ratio_error = abs(original_ratio - edited_ratio) / max(
        abs(edited_ratio),
        1e-9,
    )
    if relative_ratio_error > aspect_tolerance:
        raise ValueError(
            "geometry_mismatch: original and edited JPEG have different aspect ratios "
            f"({ow}x{oh} vs {ew}x{eh})"
        )

    resized = cv2.resize(
        original,
        (ew, eh),
        interpolation=cv2.INTER_AREA if ow >= ew and oh >= eh else cv2.INTER_CUBIC,
    )
    return resized, edited, "resized_original_to_edited"


def _float_rgb(image: np.ndarray) -> np.ndarray:
    return image.astype(np.float32) / 255.0


def _polynomial_features(rgb: np.ndarray) -> np.ndarray:
    values = rgb.reshape(-1, 3).astype(np.float64)
    r = values[:, 0]
    g = values[:, 1]
    b = values[:, 2]
    return np.column_stack(
        (
            np.ones_like(r),
            r,
            g,
            b,
            r * r,
            g * g,
            b * b,
            r * g,
            r * b,
            g * b,
        )
    )


def _sample_indices(
    pixel_count: int,
    *,
    sample_pixels: int,
    seed: int,
) -> np.ndarray:
    if pixel_count <= sample_pixels:
        return np.arange(pixel_count, dtype=np.int64)
    rng = np.random.default_rng(seed)
    return np.sort(
        rng.choice(pixel_count, size=sample_pixels, replace=False).astype(np.int64)
    )


def _train_eval_split(
    indices: np.ndarray,
    *,
    seed: int,
    train_fraction: float = 0.72,
) -> tuple[np.ndarray, np.ndarray]:
    if len(indices) < 100:
        return indices, indices

    rng = np.random.default_rng(seed ^ 0xA5A5A5A5)
    shuffled = indices.copy()
    rng.shuffle(shuffled)
    split = int(round(len(shuffled) * train_fraction))
    split = max(1, min(split, len(shuffled) - 1))
    return shuffled[:split], shuffled[split:]


def _fit_polynomial_recipe(
    original: np.ndarray,
    edited: np.ndarray,
    *,
    sample_pixels: int,
    seed: int,
    ridge_lambda: float,
) -> tuple[np.ndarray, np.ndarray]:
    x_rgb = _float_rgb(original).reshape(-1, 3)
    y_rgb = _float_rgb(edited).reshape(-1, 3)
    indices = _sample_indices(
        len(x_rgb),
        sample_pixels=sample_pixels,
        seed=seed,
    )
    train_idx, eval_idx = _train_eval_split(indices, seed=seed)

    x = _polynomial_features(x_rgb[train_idx])
    y = y_rgb[train_idx].astype(np.float64)

    regularizer = np.eye(x.shape[1], dtype=np.float64) * ridge_lambda
    regularizer[0, 0] = ridge_lambda * 0.1
    coefficients = np.linalg.solve(
        x.T @ x + regularizer,
        x.T @ y,
    )
    return coefficients, eval_idx


def _apply_recipe_float(
    rgb_float: np.ndarray,
    coefficients: np.ndarray,
    *,
    chunk_pixels: int = 1_000_000,
) -> np.ndarray:
    flat = rgb_float.reshape(-1, 3)
    output = np.empty_like(flat, dtype=np.float32)

    for start in range(0, len(flat), chunk_pixels):
        end = min(start + chunk_pixels, len(flat))
        features = _polynomial_features(flat[start:end])
        predicted = features @ coefficients
        output[start:end] = np.clip(predicted, 0.0, 1.0).astype(np.float32)

    return output.reshape(rgb_float.shape)


def _apply_recipe_uint8(
    image: np.ndarray,
    coefficients: np.ndarray,
) -> np.ndarray:
    result = _apply_recipe_float(_float_rgb(image), coefficients)
    return np.clip(np.rint(result * 255.0), 0, 255).astype(np.uint8)


def _psnr_from_rmse(rmse_255: float) -> float:
    if rmse_255 <= 1e-12:
        return float("inf")
    return 20.0 * math.log10(255.0 / rmse_255)


def _metrics(
    original: np.ndarray,
    edited: np.ndarray,
    coefficients: np.ndarray,
    eval_idx: np.ndarray,
) -> dict[str, float]:
    original_float = _float_rgb(original).reshape(-1, 3)
    edited_float = _float_rgb(edited).reshape(-1, 3)
    eval_original = original_float[eval_idx]
    eval_target = edited_float[eval_idx]

    predicted = _apply_recipe_float(
        eval_original.reshape(-1, 1, 3),
        coefficients,
    ).reshape(-1, 3)

    baseline_abs = np.abs(eval_original - eval_target)
    reconstruction_abs = np.abs(predicted - eval_target)

    baseline_mae_255 = float(np.mean(baseline_abs) * 255.0)
    reconstruction_mae_255 = float(np.mean(reconstruction_abs) * 255.0)
    reconstruction_rmse_255 = float(
        np.sqrt(np.mean(np.square(predicted - eval_target))) * 255.0
    )
    reconstruction_p95_abs_255 = float(
        np.percentile(reconstruction_abs * 255.0, 95)
    )

    luma_weights = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    predicted_luma = predicted @ luma_weights
    target_luma = eval_target @ luma_weights
    reconstruction_luma_mae_255 = float(
        np.mean(np.abs(predicted_luma - target_luma)) * 255.0
    )

    if baseline_mae_255 <= 1e-12:
        improvement = 0.0
    else:
        improvement = 1.0 - (
            reconstruction_mae_255 / baseline_mae_255
        )

    return {
        "baseline_mae_255": baseline_mae_255,
        "reconstruction_mae_255": reconstruction_mae_255,
        "reconstruction_rmse_255": reconstruction_rmse_255,
        "reconstruction_p95_abs_255": reconstruction_p95_abs_255,
        "reconstruction_luma_mae_255": reconstruction_luma_mae_255,
        "reconstruction_psnr_db": _psnr_from_rmse(reconstruction_rmse_255),
        "mae_improvement_fraction": float(improvement),
    }


def _recipe_payload(
    coefficients: np.ndarray,
    *,
    source_path: Path,
    target_path: Path,
    geometry_action: str,
    sample_pixels: int,
    ridge_lambda: float,
) -> dict:
    return {
        "schema_version": 1,
        "recipe_version": RECIPE_VERSION,
        "purpose": "jpeg_edit_representation_feasibility",
        "production_ready": False,
        "trained_model": False,
        "color_space": "sRGB_encoded_0_1",
        "transform": {
            "type": "quadratic_rgb_polynomial",
            "feature_order": list(FEATURE_NAMES),
            "output_order": ["r", "g", "b"],
            "coefficients": coefficients.tolist(),
            "clip_output_0_1": True,
        },
        "fit": {
            "source_path": str(source_path),
            "target_path": str(target_path),
            "geometry_action": geometry_action,
            "sample_pixels_requested": sample_pixels,
            "ridge_lambda": ridge_lambda,
            "note": (
                "J0 fits a global per-pixel color/tone transform directly to one "
                "known original/edited pair. It does not test prediction on unseen "
                "photos and is not a quality claim."
            ),
        },
    }


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
    y = (height - rh) // 2
    x = (width - rw) // 2
    canvas[y : y + rh, x : x + rw] = resized
    return canvas


def _comparison_strip(
    original: np.ndarray,
    edited: np.ndarray,
    reconstruction: np.ndarray,
    *,
    label: str,
    mae: float,
    target_label: str = "PHOTOGRAPHER",
) -> np.ndarray:
    tile_w = 420
    tile_h = 280
    header_h = 48
    footer_h = 34
    labels = ("ORIGINAL", target_label, "J0 RECONSTRUCTION")
    tiles = [
        _fit_tile(original, tile_w, tile_h),
        _fit_tile(edited, tile_w, tile_h),
        _fit_tile(reconstruction, tile_w, tile_h),
    ]
    body = np.concatenate(tiles, axis=1)
    canvas = np.full(
        (header_h + tile_h + footer_h, tile_w * 3, 3),
        12,
        dtype=np.uint8,
    )
    canvas[header_h : header_h + tile_h] = body

    for index, text in enumerate(labels):
        x = index * tile_w + 16
        cv2.putText(
            canvas,
            text,
            (x, 31),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.67,
            (235, 235, 235),
            1,
            cv2.LINE_AA,
        )

    footer = f"{label} | holdout-pixel MAE: {mae:.2f}/255"
    cv2.putText(
        canvas,
        footer,
        (16, header_h + tile_h + 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (190, 190, 190),
        1,
        cv2.LINE_AA,
    )
    return canvas


def _write_csv(path: Path, rows: Iterable[PairMetrics]) -> None:
    materialized = list(rows)
    if not materialized:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(materialized[0]).keys()))
        writer.writeheader()
        for row in materialized:
            writer.writerow(asdict(row))


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.median(np.asarray(values, dtype=np.float64)))


def _p90(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=np.float64), 90))


def _safe_seed(pair: dict, index: int) -> int:
    source = (
        pair.get("original_fingerprint")
        or pair.get("original_path")
        or str(index)
    )
    digest = hashlib.sha256(str(source).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big", signed=False)


def run(
    *,
    manifest_path: Path,
    output_root: Path,
    max_edge: int,
    preview_edge: int,
    sample_pixels: int,
    ridge_lambda: float,
    aspect_tolerance: float,
    jpeg_quality: int,
    limit: int | None,
    target_label: str = "PHOTOGRAPHER",
) -> dict:
    manifest = _read_json(manifest_path)
    if manifest.get("kind") != "jpeg_pairs":
        raise ValueError(
            f"Expected manifest kind 'jpeg_pairs', got {manifest.get('kind')!r}."
        )

    pairs = list(manifest.get("pairs") or [])
    if limit is not None:
        pairs = pairs[:limit]
    if not pairs:
        raise ValueError("The JPEG manifest contains no pairs.")

    output_root.mkdir(parents=True, exist_ok=True)
    recipes_dir = output_root / "recipes"
    comparisons_dir = output_root / "comparisons"
    reconstructions_dir = output_root / "reconstructions"
    recipes_dir.mkdir(parents=True, exist_ok=True)
    comparisons_dir.mkdir(parents=True, exist_ok=True)
    reconstructions_dir.mkdir(parents=True, exist_ok=True)

    completed: list[PairMetrics] = []
    skipped: list[SkippedPair] = []
    contact_rows: list[np.ndarray] = []

    for index, pair in enumerate(pairs, start=1):
        original_path = Path(pair["original_path"]).expanduser().resolve()
        edited_path = Path(pair["edited_path"]).expanduser().resolve()
        print(f"[{index:02d}/{len(pairs):02d}] {original_path.name}")

        try:
            if not original_path.is_file():
                raise ValueError("original_missing")
            if not edited_path.is_file():
                raise ValueError("edited_missing")

            if (
                pair.get("original_fingerprint")
                and pair.get("edited_fingerprint")
                and pair["original_fingerprint"] == pair["edited_fingerprint"]
                and not pair.get("identity_target_approved", False)
            ):
                raise ValueError(
                    "identical_bytes_require_explicit_identity_approval: "
                    "byte-identical pairs are not learning targets unless the "
                    "photographer/intake explicitly approved an unchanged final"
                )

            original = _read_image(original_path)
            edited = _read_image(edited_path)
            original, edited, geometry_action = _match_geometry(
                original,
                edited,
                aspect_tolerance=aspect_tolerance,
            )

            fit_original = _resize_max_edge(original, max_edge)
            fit_edited = cv2.resize(
                edited,
                (fit_original.shape[1], fit_original.shape[0]),
                interpolation=cv2.INTER_AREA,
            )

            seed = _safe_seed(pair, index)
            coefficients, eval_idx = _fit_polynomial_recipe(
                fit_original,
                fit_edited,
                sample_pixels=sample_pixels,
                seed=seed,
                ridge_lambda=ridge_lambda,
            )
            metric_values = _metrics(
                fit_original,
                fit_edited,
                coefficients,
                eval_idx,
            )

            recipe_path = recipes_dir / f"{index:03d}_{original_path.stem}_recipe.json"
            _write_json(
                recipe_path,
                _recipe_payload(
                    coefficients,
                    source_path=original_path,
                    target_path=edited_path,
                    geometry_action=geometry_action,
                    sample_pixels=sample_pixels,
                    ridge_lambda=ridge_lambda,
                ),
            )

            preview_original = _resize_max_edge(original, preview_edge)
            preview_edited = cv2.resize(
                edited,
                (preview_original.shape[1], preview_original.shape[0]),
                interpolation=cv2.INTER_AREA,
            )
            reconstruction = _apply_recipe_uint8(
                preview_original,
                coefficients,
            )
            reconstruction_path = (
                reconstructions_dir
                / f"{index:03d}_{original_path.stem}_j0.jpg"
            )
            _write_jpeg(
                reconstruction_path,
                reconstruction,
                quality=jpeg_quality,
            )

            comparison = _comparison_strip(
                preview_original,
                preview_edited,
                reconstruction,
                label=original_path.name,
                mae=metric_values["reconstruction_mae_255"],
                target_label=target_label,
            )
            comparison_path = (
                comparisons_dir
                / f"{index:03d}_{original_path.stem}_compare.jpg"
            )
            _write_jpeg(comparison_path, comparison, quality=jpeg_quality)
            contact_rows.append(comparison)

            completed.append(
                PairMetrics(
                    index=index,
                    original_path=str(original_path),
                    edited_path=str(edited_path),
                    geometry_action=geometry_action,
                    recipe_path=str(recipe_path),
                    comparison_path=str(comparison_path),
                    **metric_values,
                )
            )
        except Exception as exc:
            skipped.append(
                SkippedPair(
                    index=index,
                    original_path=str(original_path),
                    edited_path=str(edited_path),
                    reason=str(exc),
                )
            )
            print(f"  SKIPPED: {exc}")

    if contact_rows:
        contact_sheet = np.concatenate(contact_rows, axis=0)
        _write_jpeg(
            output_root / "contact_sheet.jpg",
            contact_sheet,
            quality=jpeg_quality,
        )

    if not completed:
        diagnostic = {
            "experiment": "JPEG Brain J0 — Edit Representation Feasibility",
            "production_ready": False,
            "trained_model": False,
            "quality_claim_allowed": False,
            "manifest_path": str(manifest_path),
            "pairs_requested": len(pairs),
            "pairs_completed": 0,
            "pairs_skipped": len(skipped),
            "skipped": [asdict(row) for row in skipped],
            "error": (
                "No usable edited JPEG pairs were available for J0. "
                "J0 requires decodable Original/Edited JPEG files with a real "
                "pixel difference between them."
            ),
        }
        _write_json(output_root / "summary.json", diagnostic)
        raise RuntimeError(
            "J0 has no usable edited pairs. The current fixture is suitable for "
            "pairing/manifest QA only, not edit-representation testing. Use real "
            "Original JPEG + Photographer Edited JPEG pairs."
        )

    _write_csv(output_root / "results.csv", completed)

    baseline_values = [row.baseline_mae_255 for row in completed]
    reconstruction_values = [row.reconstruction_mae_255 for row in completed]
    improvement_values = [row.mae_improvement_fraction for row in completed]
    psnr_values = [
        row.reconstruction_psnr_db
        for row in completed
        if math.isfinite(row.reconstruction_psnr_db)
    ]

    summary = {
        "schema_version": 1,
        "experiment": "JPEG Brain J0 — Edit Representation Feasibility",
        "recipe_version": RECIPE_VERSION,
        "production_ready": False,
        "trained_model": False,
        "quality_claim_allowed": False,
        "manifest_path": str(manifest_path),
        "manifest_profile_id": manifest.get("profile_id"),
        "manifest_photographer_id": manifest.get("photographer_id"),
        "manifest_event_label": manifest.get("event_label"),
        "target_label": target_label,
        "pairs_requested": len(pairs),
        "pairs_completed": len(completed),
        "pairs_skipped": len(skipped),
        "fit_configuration": {
            "max_edge": max_edge,
            "preview_edge": preview_edge,
            "sample_pixels": sample_pixels,
            "ridge_lambda": ridge_lambda,
            "aspect_tolerance": aspect_tolerance,
            "color_space": "sRGB_encoded_0_1",
            "pixel_holdout_fraction": 0.28,
        },
        "aggregate": {
            "median_baseline_mae_255": _median(baseline_values),
            "median_reconstruction_mae_255": _median(reconstruction_values),
            "p90_reconstruction_mae_255": _p90(reconstruction_values),
            "median_mae_improvement_fraction": _median(improvement_values),
            "median_reconstruction_psnr_db": _median(psnr_values),
        },
        "results": [asdict(row) for row in completed],
        "skipped": [asdict(row) for row in skipped],
        "interpretation": (
            "This experiment asks only whether one compact global JPEG transform can "
            "reconstruct each known photographer edit. It fits a separate recipe to "
            "every known pair, so it does NOT test whether a brain can predict edits "
            "for unseen photos. A visually poor reconstruction means JPEG Recipe v1 "
            "is missing expressive power; a strong reconstruction justifies moving "
            "to the next experiment: predicting these recipes from original JPEGs."
        ),
    }
    _write_json(output_root / "summary.json", summary)

    print()
    print("=" * 76)
    print("JPEG Brain J0 — Edit Representation Feasibility")
    print("=" * 76)
    print(f"Manifest:                    {manifest_path}")
    print(f"Pairs completed:             {len(completed)}")
    print(f"Pairs skipped:               {len(skipped)}")
    print(
        "Median no-edit MAE:         "
        f"{summary['aggregate']['median_baseline_mae_255'] or 0.0:.2f}/255"
    )
    print(
        "Median J0 reconstruction:   "
        f"{summary['aggregate']['median_reconstruction_mae_255'] or 0.0:.2f}/255"
    )
    improvement = summary["aggregate"]["median_mae_improvement_fraction"]
    print(
        "Median MAE improvement:     "
        f"{(improvement or 0.0) * 100.0:.1f}%"
    )
    print(f"Output:                      {output_root}")
    print()
    print("Open contact_sheet.jpg and inspect Photographer vs J0 Reconstruction.")
    print("This is a representation test only; no JPEG prediction model was trained.")

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "JPEG Brain J0: fit a compact global JPEG edit representation to each "
            "known original/photographer pair and measure reconstruction capacity."
        )
    )
    parser.add_argument("--manifest", required=True, help="Path to JPEG manifest.json")
    parser.add_argument("--output", required=True, help="Destination experiment folder")
    parser.add_argument(
        "--max-edge",
        type=int,
        default=1000,
        help="Maximum edge used for fitting and metrics (default: 1000)",
    )
    parser.add_argument(
        "--preview-edge",
        type=int,
        default=1200,
        help="Maximum edge for visual reconstructions (default: 1200)",
    )
    parser.add_argument(
        "--sample-pixels",
        type=int,
        default=120000,
        help="Maximum sampled pixels per pair (default: 120000)",
    )
    parser.add_argument(
        "--ridge-lambda",
        type=float,
        default=1e-4,
        help="Ridge regularization for polynomial coefficients (default: 1e-4)",
    )
    parser.add_argument(
        "--aspect-tolerance",
        type=float,
        default=0.01,
        help="Maximum relative aspect-ratio difference before skipping (default: 0.01)",
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=95,
        help="Output JPEG quality for previews (default: 95)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit for quick smoke tests",
    )
    parser.add_argument(
        "--target-label",
        default="PHOTOGRAPHER",
        help="Label shown above the target image in comparison strips",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve(strict=True)
    output_root = Path(args.output).expanduser().resolve()

    run(
        manifest_path=manifest_path,
        output_root=output_root,
        max_edge=max(128, args.max_edge),
        preview_edge=max(128, args.preview_edge),
        sample_pixels=max(1000, args.sample_pixels),
        ridge_lambda=max(0.0, args.ridge_lambda),
        aspect_tolerance=max(0.0, args.aspect_tolerance),
        jpeg_quality=min(100, max(50, args.jpeg_quality)),
        limit=max(1, args.limit) if args.limit is not None else None,
        target_label=args.target_label.strip() or "PHOTOGRAPHER",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
