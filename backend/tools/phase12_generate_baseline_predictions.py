from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.brain_v2.training.baseline import (
    fit_simple_baseline,
    generate_validation_predictions,
)
from app.brain_v2.training.dataset_manifest import DatasetImportManifest
from app.brain_v2.training.event_split import EventSafeSplitManifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--split", required=True, type=Path)
    parser.add_argument(
        "--strategy",
        choices=("median", "mean"),
        default="median",
    )
    parser.add_argument(
        "--predictions-output",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--metadata-output",
        type=Path,
        default=None,
    )
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    split_path = args.split.resolve()

    manifest = DatasetImportManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    split = EventSafeSplitManifest.model_validate_json(
        split_path.read_text(encoding="utf-8")
    )

    baseline = fit_simple_baseline(
        manifest=manifest,
        split=split,
        strategy=args.strategy,
    )
    bundle = generate_validation_predictions(
        manifest=manifest,
        split=split,
        baseline=baseline,
    )

    docs_runtime = Path.cwd().resolve().parent / "docs" / "runtime"
    predictions_output = (
        args.predictions_output.resolve()
        if args.predictions_output
        else docs_runtime
        / f"phase12_baseline_{args.strategy}_predictions.json"
    )
    metadata_output = (
        args.metadata_output.resolve()
        if args.metadata_output
        else docs_runtime
        / f"phase12_baseline_{args.strategy}_metadata.json"
    )

    predictions_output.parent.mkdir(parents=True, exist_ok=True)
    metadata_output.parent.mkdir(parents=True, exist_ok=True)

    predictions_output.write_text(
        json.dumps(
            [
                item.model_dump(mode="json")
                for item in bundle.predictions
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    metadata_output.write_text(
        json.dumps(
            {
                "schema_version": "phase12-baseline-metadata-v1",
                "baseline": bundle.baseline.model_dump(mode="json"),
                "validation_sample_count": bundle.validation_sample_count,
                "predictions_file": str(predictions_output),
                "guardrails": [
                    "Baseline is fitted from train samples only.",
                    "Validation target values are never used during baseline fitting.",
                    "Predictions cover the validation cohort only.",
                    "This baseline is a reference point, not a production Brain.",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=== Phase 12 Simple Baseline ===")
    print(f"strategy: {baseline.strategy}")
    print(f"baseline_id: {baseline.baseline_id}")
    print(f"train samples: {baseline.train_sample_count}")
    print(f"validation samples: {bundle.validation_sample_count}")
    print("fitted values:")
    for field, value in baseline.fitted_values.items():
        print(f"  {field}: {value}")
    print(f"Predictions: {predictions_output}")
    print(f"Metadata: {metadata_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
