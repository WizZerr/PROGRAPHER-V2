from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import cv2
import numpy as np

from jpeg_j0_feasibility import (
    FEATURE_NAMES,
    _apply_recipe_uint8,
    _write_jpeg,
    run as run_j0,
)


SYNTHETIC_SCHEMA_VERSION = 1
SUPPORTED_CASES = (
    "warm_clean",
    "cool_moody",
    "bright_soft",
    "deep_contrast",
    "magenta_bias",
    "cyan_bias",
    "warm_highlights",
    "neutral_punch",
)
CHALLENGE_CASES = (
    "local_vignette",
    "local_center_lift",
    "mixed_light_gradient",
    "selective_red_boost",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _identity_coefficients() -> np.ndarray:
    coefficients = np.zeros((len(FEATURE_NAMES), 3), dtype=np.float64)
    coefficients[1, 0] = 1.0
    coefficients[2, 1] = 1.0
    coefficients[3, 2] = 1.0
    return coefficients


def _recipe(case_name: str) -> np.ndarray:
    c = _identity_coefficients()

    if case_name == "warm_clean":
        c[0] += [0.018, 0.006, -0.014]
        c[1, 0] += 0.040
        c[3, 2] -= 0.035
        c[4, 0] += 0.020
        c[6, 2] -= 0.012
    elif case_name == "cool_moody":
        c[0] += [-0.018, -0.010, 0.010]
        c[1, 0] -= 0.030
        c[3, 2] += 0.050
        c[4, 0] -= 0.018
        c[6, 2] += 0.018
    elif case_name == "bright_soft":
        c[0] += [0.042, 0.040, 0.038]
        c[1, 0] -= 0.035
        c[2, 1] -= 0.030
        c[3, 2] -= 0.025
        c[4, 0] -= 0.020
        c[5, 1] -= 0.020
        c[6, 2] -= 0.018
    elif case_name == "deep_contrast":
        c[0] += [-0.030, -0.026, -0.024]
        c[1, 0] += 0.095
        c[2, 1] += 0.090
        c[3, 2] += 0.085
        c[4, 0] += 0.040
        c[5, 1] += 0.035
        c[6, 2] += 0.030
    elif case_name == "magenta_bias":
        c[0] += [0.014, -0.010, 0.012]
        c[1, 0] += 0.025
        c[2, 1] -= 0.018
        c[3, 2] += 0.018
        c[7, 0] += 0.018
        c[9, 2] += 0.012
    elif case_name == "cyan_bias":
        c[0] += [-0.012, 0.008, 0.016]
        c[1, 0] -= 0.022
        c[2, 1] += 0.020
        c[3, 2] += 0.030
        c[8, 2] += 0.014
    elif case_name == "warm_highlights":
        c[0] += [0.004, 0.000, -0.004]
        c[4, 0] += 0.080
        c[5, 1] += 0.025
        c[6, 2] -= 0.035
        c[8, 0] += 0.018
    elif case_name == "neutral_punch":
        c[0] += [-0.012, -0.012, -0.012]
        c[1, 0] += 0.060
        c[2, 1] += 0.060
        c[3, 2] += 0.060
        c[4, 0] += 0.018
        c[5, 1] += 0.018
        c[6, 2] += 0.018
        c[7, 0] += 0.008
        c[8, 2] += 0.008
    else:
        raise KeyError(case_name)

    return c


def _make_scene(index: int, width: int = 1280, height: int = 853) -> np.ndarray:
    rng = np.random.default_rng(9000 + index)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    x = xx / max(width - 1, 1)
    y = yy / max(height - 1, 1)

    r = 0.10 + 0.50 * x + 0.16 * (1.0 - y)
    g = 0.08 + 0.38 * x + 0.24 * y
    b = 0.12 + 0.28 * (1.0 - x) + 0.34 * y

    for light_index in range(10):
        cx = rng.uniform(0.05, 0.95)
        cy = rng.uniform(0.05, 0.90)
        sigma = rng.uniform(0.015, 0.090)
        energy = rng.uniform(0.05, 0.22)
        gaussian = np.exp(
            -((x - cx) ** 2 + (y - cy) ** 2) / (2.0 * sigma * sigma)
        )
        tint = rng.uniform(0.75, 1.25, size=3)
        r += gaussian * energy * tint[0]
        g += gaussian * energy * tint[1]
        b += gaussian * energy * tint[2]

    rgb = np.stack([r, g, b], axis=-1)
    rgb += rng.normal(0.0, 0.008, size=rgb.shape).astype(np.float32)
    rgb = np.clip(rgb, 0.0, 1.0)

    image = np.rint(rgb * 255.0).astype(np.uint8)

    skin = tuple(int(v) for v in (190, 132, 110))
    cv2.ellipse(
        image,
        (int(width * (0.25 + 0.04 * (index % 4))), int(height * 0.46)),
        (int(width * 0.075), int(height * 0.13)),
        8 - index,
        0,
        360,
        skin,
        -1,
    )
    cv2.rectangle(
        image,
        (int(width * 0.60), int(height * 0.55)),
        (int(width * 0.88), int(height * 0.82)),
        (45 + index * 2, 76 + index, 118 + index * 3),
        -1,
    )
    cv2.circle(
        image,
        (int(width * 0.76), int(height * 0.28)),
        int(min(width, height) * 0.08),
        (224, 197, 148),
        -1,
    )

    return image


def _local_challenge(
    image: np.ndarray,
    case_name: str,
) -> np.ndarray:
    rgb = image.astype(np.float32) / 255.0
    height, width = image.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    x = xx / max(width - 1, 1)
    y = yy / max(height - 1, 1)

    if case_name == "local_vignette":
        radius2 = ((x - 0.5) / 0.72) ** 2 + ((y - 0.5) / 0.72) ** 2
        gain = np.clip(1.05 - 0.34 * radius2, 0.62, 1.05)
        rgb *= gain[..., None]
    elif case_name == "local_center_lift":
        center = np.exp(
            -(
                ((x - 0.48) ** 2) / (2 * 0.18**2)
                + ((y - 0.45) ** 2) / (2 * 0.20**2)
            )
        )
        rgb += center[..., None] * 0.12
    elif case_name == "mixed_light_gradient":
        warm = np.clip(1.0 - x, 0.0, 1.0)
        cool = np.clip(x, 0.0, 1.0)
        rgb[..., 0] += warm * 0.085
        rgb[..., 2] += cool * 0.090
        rgb[..., 1] -= np.abs(x - 0.5) * 0.020
    elif case_name == "selective_red_boost":
        mask = (
            (rgb[..., 0] > rgb[..., 1] * 1.12)
            & (rgb[..., 0] > rgb[..., 2] * 1.10)
        ).astype(np.float32)
        mask = cv2.GaussianBlur(mask, (0, 0), 3.0)
        rgb[..., 0] += mask * 0.10
        rgb[..., 1] -= mask * 0.025
        rgb[..., 2] -= mask * 0.020
    else:
        raise KeyError(case_name)

    return np.clip(np.rint(rgb * 255.0), 0, 255).astype(np.uint8)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.median(np.asarray(values, dtype=np.float64)))


def _build_fixture(root: Path, jpeg_quality: int) -> tuple[Path, dict[int, dict]]:
    originals = root / "ORIGINALS"
    edits = root / "EDITS"
    originals.mkdir(parents=True, exist_ok=True)
    edits.mkdir(parents=True, exist_ok=True)

    pairs: list[dict] = []
    metadata: dict[int, dict] = {}
    case_names = list(SUPPORTED_CASES) + list(CHALLENGE_CASES)

    for index, case_name in enumerate(case_names, start=1):
        original = _make_scene(index)
        if case_name in SUPPORTED_CASES:
            coefficients = _recipe(case_name)
            edited = _apply_recipe_uint8(original, coefficients)
            category = "supported_global"
            true_recipe = coefficients.tolist()
        else:
            base_case = SUPPORTED_CASES[(index - 1) % len(SUPPORTED_CASES)]
            coefficients = _recipe(base_case)
            edited = _apply_recipe_uint8(original, coefficients)
            edited = _local_challenge(edited, case_name)
            category = "challenge_local"
            true_recipe = coefficients.tolist()

        name = f"SYN_{index:03d}_{case_name}.jpg"
        original_path = originals / name
        edited_path = edits / name
        _write_jpeg(original_path, original, quality=jpeg_quality)
        _write_jpeg(edited_path, edited, quality=jpeg_quality)

        pair = {
            "original_path": str(original_path.resolve()),
            "edited_path": str(edited_path.resolve()),
            "original_relative_path": name,
            "edited_relative_path": name,
            "original_fingerprint": _sha256(original_path),
            "edited_fingerprint": _sha256(edited_path),
            "synthetic_case": case_name,
            "synthetic_category": category,
        }
        pairs.append(pair)
        metadata[index] = {
            "case": case_name,
            "category": category,
            "base_recipe_coefficients": true_recipe,
        }

    manifest = {
        "schema_version": 1,
        "kind": "jpeg_pairs",
        "profile_id": "jpeg-j0-synthetic-benchmark",
        "created_at": "deterministic-synthetic",
        "photographer_id": "synthetic-ground-truth",
        "event_label": "jpeg-j0-synthetic",
        "originals_root": str(originals.resolve()),
        "edits_root": str(edits.resolve()),
        "pairs": pairs,
    }
    manifest_path = root / "manifest.json"
    _write_json(manifest_path, manifest)
    _write_json(
        root / "ground_truth.json",
        {
            "schema_version": SYNTHETIC_SCHEMA_VERSION,
            "feature_order": list(FEATURE_NAMES),
            "cases": metadata,
            "note": (
                "supported_global cases are generated by the same transform family "
                "J0 is allowed to fit. challenge_local cases add spatial/selective "
                "edits that a single global polynomial should not represent perfectly."
            ),
        },
    )
    return manifest_path, metadata


def _summarize_groups(j0_summary: dict, metadata: dict[int, dict]) -> dict:
    groups = {
        "supported_global": [],
        "challenge_local": [],
    }
    per_case = []

    for result in j0_summary.get("results", []):
        index = int(result["index"])
        case = metadata[index]
        row = {
            "index": index,
            "case": case["case"],
            "category": case["category"],
            "baseline_mae_255": result["baseline_mae_255"],
            "reconstruction_mae_255": result["reconstruction_mae_255"],
            "mae_improvement_fraction": result["mae_improvement_fraction"],
            "reconstruction_psnr_db": result["reconstruction_psnr_db"],
            "comparison_path": result["comparison_path"],
        }
        groups[case["category"]].append(row)
        per_case.append(row)

    aggregate = {}
    for name, rows in groups.items():
        aggregate[name] = {
            "count": len(rows),
            "median_baseline_mae_255": _median(
                [float(row["baseline_mae_255"]) for row in rows]
            ),
            "median_reconstruction_mae_255": _median(
                [float(row["reconstruction_mae_255"]) for row in rows]
            ),
            "median_mae_improvement_fraction": _median(
                [float(row["mae_improvement_fraction"]) for row in rows]
            ),
        }

    supported = aggregate["supported_global"]
    challenge = aggregate["challenge_local"]
    supported_mae = supported["median_reconstruction_mae_255"]
    challenge_mae = challenge["median_reconstruction_mae_255"]

    sanity_pass = bool(
        supported["count"] == len(SUPPORTED_CASES)
        and supported_mae is not None
        and supported_mae <= 3.0
        and supported["median_mae_improvement_fraction"] is not None
        and supported["median_mae_improvement_fraction"] >= 0.80
    )
    limitation_visible = bool(
        challenge["count"] == len(CHALLENGE_CASES)
        and challenge_mae is not None
        and supported_mae is not None
        and challenge_mae > supported_mae + 0.75
    )

    return {
        "sanity_pass": sanity_pass,
        "limitation_visible": limitation_visible,
        "thresholds": {
            "supported_median_reconstruction_mae_255_max": 3.0,
            "supported_median_mae_improvement_fraction_min": 0.80,
            "challenge_should_exceed_supported_by_mae_255": 0.75,
        },
        "aggregate": aggregate,
        "cases": per_case,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a deterministic synthetic JPEG benchmark and run J0 against "
            "known global edits plus deliberately non-global challenge edits."
        )
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Destination benchmark folder",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete the destination first if it already exists",
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=98,
        help="Synthetic source/target JPEG quality (default: 98)",
    )
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    if args.clean and output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    fixture_root = output / "fixture"
    results_root = output / "j0_results"
    manifest_path, metadata = _build_fixture(
        fixture_root,
        jpeg_quality=min(100, max(85, args.jpeg_quality)),
    )

    j0_summary = run_j0(
        manifest_path=manifest_path,
        output_root=results_root,
        max_edge=1000,
        preview_edge=1200,
        sample_pixels=120000,
        ridge_lambda=1e-4,
        aspect_tolerance=0.01,
        jpeg_quality=95,
        limit=None,
        target_label="GROUND TRUTH",
    )

    benchmark = {
        "schema_version": SYNTHETIC_SCHEMA_VERSION,
        "experiment": "JPEG Brain J0 — Synthetic Ground Truth Benchmark",
        "production_ready": False,
        "quality_claim_allowed": False,
        "purpose": (
            "Engineering validation of the J0 edit representation and evaluation "
            "pipeline before real photographer JPEG pairs are available."
        ),
        "manifest_path": str(manifest_path),
        "j0_summary_path": str(results_root / "summary.json"),
        **_summarize_groups(j0_summary, metadata),
    }
    _write_json(output / "benchmark_summary.json", benchmark)

    supported = benchmark["aggregate"]["supported_global"]
    challenge = benchmark["aggregate"]["challenge_local"]

    print()
    print("=" * 78)
    print("JPEG Brain J0 — Synthetic Ground Truth Benchmark")
    print("=" * 78)
    print(f"Supported cases:                 {supported['count']}")
    print(
        "Supported median J0 MAE:         "
        f"{supported['median_reconstruction_mae_255'] or 0.0:.2f}/255"
    )
    print(
        "Supported median improvement:    "
        f"{(supported['median_mae_improvement_fraction'] or 0.0) * 100.0:.1f}%"
    )
    print(f"Challenge cases:                 {challenge['count']}")
    print(
        "Challenge median J0 MAE:         "
        f"{challenge['median_reconstruction_mae_255'] or 0.0:.2f}/255"
    )
    print(
        "J0 global-recipe sanity:         "
        + ("PASS" if benchmark["sanity_pass"] else "FAIL")
    )
    print(
        "Local-edit limitation visible:   "
        + ("YES" if benchmark["limitation_visible"] else "NOT CLEAR")
    )
    print(f"Benchmark output:                {output}")
    print()
    print(
        "Inspect j0_results\\contact_sheet.jpg. The middle column is synthetic "
        "GROUND TRUTH, not a photographer edit."
    )

    return 0 if benchmark["sanity_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
