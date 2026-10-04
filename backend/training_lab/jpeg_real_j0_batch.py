from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.datasets.jpeg_integrity import (
    JPEG_COLOR_CONTRACT_VERSION,
    load_and_validate_dataset_snapshot,
)
from app.rendering.jpeg_renderer import (
    JPEG_EDIT_RECIPE_VERSION as RECIPE_VERSION,
    validate_jpeg_edit_recipe,
)
from app.evaluation.artifact_provenance import (
    J0_TARGET_FEATURE_CONTRACT_VERSION,
    RENDERER_CONTRACT_VERSION,
    target_semantics_sha256,
    dependency_lock_fingerprint,
    ensure_immutable_artifact_dir,
    resolve_code_revision,
    sha256_file,
    target_bundle_provenance,
    write_immutable_json,
)
from jpeg_j0_feasibility import run as run_j0


SCHEMA_VERSION = 1
ALLOWED_SPLITS = {"train", "validation", "test"}


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


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.median(np.asarray(values, dtype=np.float64)))


def _p90(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=np.float64), 90))


def _requested_splits(mode: str, unlock_test: bool) -> set[str]:
    if mode == "train":
        return {"train"}
    if mode == "validation":
        return {"validation"}
    if mode == "train-validation":
        return {"train", "validation"}
    if mode == "test":
        if not unlock_test:
            raise ValueError(
                "Test is locked. Re-run with --unlock-test only for a deliberate final audit."
            )
        return {"test"}
    if mode == "all":
        if not unlock_test:
            raise ValueError(
                "Mode 'all' includes locked Test. Add --unlock-test only for a deliberate audit."
            )
        return {"train", "validation", "test"}
    raise ValueError(f"unsupported split mode: {mode}")


def _canonical(path: str) -> str:
    return str(Path(path).expanduser().resolve()).casefold()


def _load_recipe(path: str) -> dict:
    payload = _read_json(Path(path))
    try:
        validate_jpeg_edit_recipe(payload)
    except ValueError as exc:
        raise ValueError(f"invalid JPEG EditRecipe {path}: {exc}") from exc
    return payload


def run_batch(
    *,
    dataset_manifest_path: Path,
    output_root: Path,
    split_mode: str,
    unlock_test: bool,
    max_edge: int,
    preview_edge: int,
    sample_pixels: int,
    ridge_lambda: float,
    jpeg_quality: int,
    code_revision: str | None = None,
) -> dict:
    dataset = _read_json(dataset_manifest_path)
    if dataset.get("kind") != "jpeg_real_event_dataset":
        raise ValueError(
            "Expected dataset_manifest.json created by jpeg_real_dataset_intake.py"
        )

    snapshot_path = dataset.get("dataset_snapshot_path")
    snapshot_id = dataset.get("dataset_snapshot_id")
    if not snapshot_path or not snapshot_id:
        raise ValueError(
            "Dataset predates the frozen snapshot contract; re-run intake before J0."
        )
    load_and_validate_dataset_snapshot(
        snapshot_path,
        expected_snapshot_id=snapshot_id,
    )

    requested = _requested_splits(split_mode, unlock_test)
    output_root.mkdir(parents=True, exist_ok=True)

    pair_lookup = {
        _canonical(pair["original_path"]): pair
        for pair in dataset.get("pairs", [])
        if pair.get("usable_for_recipe_fit")
    }

    selected_events = [
        event
        for event in dataset.get("events", [])
        if event.get("split") in requested
        and event.get("usable_pairs", 0) > 0
        and event.get("j0_manifest_path")
    ]
    if not selected_events:
        raise ValueError(
            "No usable event manifests exist for the requested split selection."
        )

    event_summaries: list[dict] = []
    recipe_targets: list[dict] = []
    flat_results: list[dict] = []

    for event in selected_events:
        event_id = event["event_id"]
        split = event["split"]
        manifest_path = Path(event["j0_manifest_path"]).expanduser().resolve(strict=True)
        event_output = output_root / split / event_id

        print()
        print(f"Running J0: {split}/{event_id}")
        summary = run_j0(
            manifest_path=manifest_path,
            output_root=event_output,
            max_edge=max_edge,
            preview_edge=preview_edge,
            sample_pixels=sample_pixels,
            ridge_lambda=ridge_lambda,
            aspect_tolerance=float(dataset.get("aspect_tolerance", 0.01)),
            jpeg_quality=jpeg_quality,
            limit=None,
            target_label="PHOTOGRAPHER",
        )

        aggregate = dict(summary.get("aggregate") or {})
        event_summary = {
            "event_id": event_id,
            "split": split,
            "pairs_completed": summary.get("pairs_completed", 0),
            "pairs_skipped": summary.get("pairs_skipped", 0),
            **aggregate,
            "event_output": str(event_output),
            "contact_sheet_path": str(event_output / "contact_sheet.jpg"),
        }
        event_summaries.append(event_summary)

        for result in summary.get("results", []):
            pair = pair_lookup.get(_canonical(result["original_path"]))
            if pair is None:
                raise RuntimeError(
                    "J0 result could not be mapped back to the frozen dataset pair: "
                    + result["original_path"]
                )

            recipe = _load_recipe(result["recipe_path"])
            target = {
                "pair_id": pair["pair_id"],
                "event_id": event_id,
                "split": split,
                "original_path": pair["original_path"],
                "edited_path": pair["edited_path"],
                "original_sha256": pair["original_sha256"],
                "edited_sha256": pair["edited_sha256"],
                "recipe_version": recipe.get("recipe_version"),
                "recipe_transform": recipe.get("transform"),
                "j0_metrics": {
                    "baseline_mae_255": result["baseline_mae_255"],
                    "reconstruction_mae_255": result["reconstruction_mae_255"],
                    "reconstruction_rmse_255": result["reconstruction_rmse_255"],
                    "reconstruction_p95_abs_255": result[
                        "reconstruction_p95_abs_255"
                    ],
                    "reconstruction_luma_mae_255": result[
                        "reconstruction_luma_mae_255"
                    ],
                    "reconstruction_psnr_db": result["reconstruction_psnr_db"],
                    "mae_improvement_fraction": result["mae_improvement_fraction"],
                },
            }
            recipe_targets.append(target)
            flat_results.append(
                {
                    "pair_id": pair["pair_id"],
                    "event_id": event_id,
                    "split": split,
                    "original_path": pair["original_path"],
                    "edited_path": pair["edited_path"],
                    **target["j0_metrics"],
                }
            )

    reconstruction_mae = [
        float(row["reconstruction_mae_255"]) for row in flat_results
    ]
    baseline_mae = [float(row["baseline_mae_255"]) for row in flat_results]
    improvements = [
        float(row["mae_improvement_fraction"]) for row in flat_results
    ]

    summary = {
        "schema_version": SCHEMA_VERSION,
        "experiment": "JPEG Brain J0 — Real Photographer Representation Batch",
        "created_at": _utc_now(),
        "production_ready": False,
        "trained_prediction_model": False,
        "real_photographer_quality_claim_allowed": False,
        "dataset_manifest_path": str(dataset_manifest_path),
        "photographer_id": dataset.get("photographer_id"),
        "split_mode": split_mode,
        "test_unlocked": bool(unlock_test and "test" in requested),
        "requested_splits": sorted(requested),
        "events_completed": len(event_summaries),
        "pairs_completed": len(flat_results),
        "aggregate": {
            "median_baseline_mae_255": _median(baseline_mae),
            "median_reconstruction_mae_255": _median(reconstruction_mae),
            "p90_reconstruction_mae_255": _p90(reconstruction_mae),
            "median_mae_improvement_fraction": _median(improvements),
        },
        "events": event_summaries,
        "interpretation": (
            "J0 fits a separate recipe while seeing each known Original/Photographer "
            "pair. This tests representation capacity only. It does not test whether "
            "a Brain can predict an edit for an unseen photo."
        ),
    }

    target_payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": "jpeg_j0_recipe_targets",
        "created_at": _utc_now(),
        "dataset_manifest_path": str(dataset_manifest_path),
        "dataset_snapshot_id": dataset.get("dataset_snapshot_id"),
        "photographer_id": dataset.get("photographer_id"),
        "split_mode": split_mode,
        "test_unlocked": bool(unlock_test and "test" in requested),
        "targets": recipe_targets,
        "note": (
            "Per-image inverse-fit J0 targets. Candidate prediction models may train "
            "only on Train targets and select changes on Validation. Locked Test "
            "targets must not be used for tuning."
        ),
    }

    resolved_revision = resolve_code_revision(code_revision)
    dependency = dependency_lock_fingerprint()
    target_config = {
        "max_edge": int(max_edge),
        "preview_edge": int(preview_edge),
        "sample_pixels": int(sample_pixels),
        "ridge_lambda": float(ridge_lambda),
        "jpeg_quality": int(jpeg_quality),
        "aspect_tolerance": float(dataset.get("aspect_tolerance", 0.01)),
    }
    provenance = target_bundle_provenance(
        dataset_snapshot_id=str(dataset.get("dataset_snapshot_id") or ""),
        dataset_manifest_sha256=sha256_file(dataset_manifest_path),
        target_semantics_sha256_value=target_semantics_sha256(target_payload),
        code_revision=resolved_revision,
        dependency_lock_sha256=dependency["dependency_lock_sha256"],
        color_contract_version=str(
            dataset.get("color_contract_version")
            or JPEG_COLOR_CONTRACT_VERSION
        ),
        feature_contract_version=J0_TARGET_FEATURE_CONTRACT_VERSION,
        recipe_contract_version=RECIPE_VERSION,
        renderer_contract_version=RENDERER_CONTRACT_VERSION,
        config=target_config,
        split_mode=split_mode,
    )
    target_payload["provenance"] = provenance

    target_bundle_dir = ensure_immutable_artifact_dir(
        output_root / "target_bundles",
        provenance["artifact_id"],
    )
    target_bundle_path = target_bundle_dir / "recipe_targets.json"
    write_immutable_json(target_bundle_path, target_payload)

    summary["target_artifact_id"] = provenance["artifact_id"]
    summary["target_bundle_path"] = str(target_bundle_path)
    summary["target_provenance"] = provenance
    _write_json(output_root / "summary.json", summary)
    _write_json(
        output_root / "latest_target_bundle.json",
        {
            "artifact_id": provenance["artifact_id"],
            "recipe_targets_path": str(target_bundle_path),
            "artifact_sha256": sha256_file(target_bundle_path),
        },
    )
    _write_csv(output_root / "pair_results.csv", flat_results)
    _write_csv(output_root / "event_results.csv", event_summaries)

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run J0 representation fitting across a frozen real JPEG event dataset "
            "and export versioned per-image recipe targets."
        )
    )
    parser.add_argument(
        "--dataset-manifest",
        required=True,
        help="dataset_manifest.json from jpeg_real_dataset_intake.py",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--split",
        choices=("train", "validation", "train-validation", "test", "all"),
        default="train-validation",
        help="Default keeps locked Test untouched.",
    )
    parser.add_argument(
        "--unlock-test",
        action="store_true",
        help="Explicitly allow a deliberate final audit on locked Test events.",
    )
    parser.add_argument("--max-edge", type=int, default=1000)
    parser.add_argument("--preview-edge", type=int, default=1200)
    parser.add_argument("--sample-pixels", type=int, default=120000)
    parser.add_argument("--ridge-lambda", type=float, default=1e-4)
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
    output_root = Path(args.output).expanduser().resolve()

    summary = run_batch(
        dataset_manifest_path=dataset_manifest_path,
        output_root=output_root,
        split_mode=args.split,
        unlock_test=bool(args.unlock_test),
        max_edge=max(128, int(args.max_edge)),
        preview_edge=max(128, int(args.preview_edge)),
        sample_pixels=max(1000, int(args.sample_pixels)),
        ridge_lambda=max(0.0, float(args.ridge_lambda)),
        jpeg_quality=min(100, max(50, int(args.jpeg_quality))),
        code_revision=args.code_revision,
    )

    print()
    print("=" * 80)
    print("JPEG Brain J0 — Real Photographer Representation Batch")
    print("=" * 80)
    print(f"Events completed:                {summary['events_completed']}")
    print(f"Pairs completed:                 {summary['pairs_completed']}")
    print(
        "Median no-edit MAE:              "
        f"{summary['aggregate']['median_baseline_mae_255'] or 0.0:.2f}/255"
    )
    print(
        "Median J0 reconstruction MAE:    "
        f"{summary['aggregate']['median_reconstruction_mae_255'] or 0.0:.2f}/255"
    )
    print(
        "Median MAE improvement:          "
        f"{(summary['aggregate']['median_mae_improvement_fraction'] or 0.0) * 100.0:.1f}%"
    )
    print(f"Split mode:                      {summary['split_mode']}")
    print(f"Target artifact:                 {summary['target_artifact_id']}")
    print(f"Target bundle:                   {summary['target_bundle_path']}")
    print(f"Output:                          {output_root}")
    print()
    print("Representation-only result. No unseen-photo prediction model was trained.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
