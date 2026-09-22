from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.brain_v2.training.dataset_manifest import DatasetImportManifest
from app.brain_v2.training.evaluation import (
    CandidatePrediction,
    compare_candidate_to_baseline,
    evaluate_candidate_predictions,
)
from app.brain_v2.training.event_split import EventSafeSplitManifest


def _load_predictions(path: Path) -> list[CandidatePrediction]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(
            f"Could not read prediction file {path}: "
            f"{type(exc).__name__}: {exc}"
        )

    if not isinstance(payload, list):
        raise SystemExit(
            f"Prediction file must contain a JSON list: {path}"
        )

    try:
        return [
            CandidatePrediction.model_validate(item)
            for item in payload
        ]
    except Exception as exc:
        raise SystemExit(
            f"Invalid prediction file {path}: "
            f"{type(exc).__name__}: {exc}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--split", required=True, type=Path)
    parser.add_argument(
        "--candidate",
        action="append",
        required=True,
        help="NAME=path-to-predictions.json; repeatable",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="Candidate NAME to use as the baseline comparison.",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    split_path = args.split.resolve()

    manifest = DatasetImportManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    split = EventSafeSplitManifest.model_validate_json(
        split_path.read_text(encoding="utf-8")
    )

    candidate_specs: list[tuple[str, Path]] = []
    for raw in args.candidate:
        if "=" not in raw:
            raise SystemExit(
                "--candidate must use NAME=path.json"
            )
        name, path_text = raw.split("=", 1)
        name = name.strip()
        path = Path(path_text).resolve()
        if not name or not path.is_file():
            raise SystemExit(
                f"Invalid candidate specification: {raw}"
            )
        candidate_specs.append((name, path))

    if len({name for name, _ in candidate_specs}) != len(candidate_specs):
        raise SystemExit("Candidate names must be unique")

    evaluations = {}
    for name, path in candidate_specs:
        evaluation = evaluate_candidate_predictions(
            manifest=manifest,
            split=split,
            candidate_name=name,
            predictions=_load_predictions(path),
        )
        evaluations[name] = evaluation

    comparisons = []
    if args.baseline is not None:
        if args.baseline not in evaluations:
            raise SystemExit(
                f"Baseline candidate not supplied: {args.baseline}"
            )
        baseline = evaluations[args.baseline]
        for name, evaluation in evaluations.items():
            if name == args.baseline:
                continue
            comparisons.append(
                compare_candidate_to_baseline(
                    candidate=evaluation,
                    baseline=baseline,
                )
            )

    output_payload = {
        "schema_version": "phase12-evaluation-report-v1",
        "dataset_id": manifest.dataset_id,
        "split_id": split.split_id,
        "evaluations": {
            name: evaluation.model_dump(mode="json")
            for name, evaluation in evaluations.items()
        },
        "baseline": args.baseline,
        "comparisons": [
            item.model_dump(mode="json")
            for item in comparisons
        ],
        "guardrails": [
            "Every candidate is evaluated on the exact same validation sample IDs.",
            "Metrics are reported per target because Exposure, Kelvin, and Tint use different units.",
            "This report does not train a model or select a quality winner by itself.",
            "Visual Lightroom review remains required before promotion.",
        ],
    }

    output = (
        args.output.resolve()
        if args.output
        else Path.cwd().resolve().parent
        / "docs"
        / "runtime"
        / "phase12_evaluation_report.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            output_payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=== Phase 12 Evaluation Harness ===")
    print(f"dataset_id: {manifest.dataset_id}")
    print(f"split_id: {split.split_id}")
    print(
        f"candidates: {', '.join(evaluations.keys())}"
    )
    if args.baseline:
        print(f"baseline: {args.baseline}")
    for name, evaluation in evaluations.items():
        print(f"[{name}]")
        for target, metrics in evaluation.metrics.items():
            print(
                f"  {target}: "
                f"MAE={metrics.mae:.6f} "
                f"MedianAE={metrics.median_absolute_error:.6f} "
                f"P90={metrics.p90_absolute_error:.6f} "
                f"P95={metrics.p95_absolute_error:.6f}"
            )
    print(f"Report: {output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
