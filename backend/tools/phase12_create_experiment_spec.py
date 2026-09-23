from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.brain_v2.models.edit_targets import WhiteBalanceTargetMode
from app.brain_v2.training.dataset_manifest import DatasetImportManifest
from app.brain_v2.training.event_split import EventSafeSplitManifest
from app.brain_v2.training.experiment_contract import (
    EstimatorSpec,
    RepresentationSpec,
    build_candidate_experiment_spec,
)


def _json_object(text: str) -> dict:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid JSON object: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise argparse.ArgumentTypeError("value must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--split", required=True, type=Path)
    parser.add_argument("--candidate-name", required=True)
    parser.add_argument(
        "--candidate-family",
        required=True,
        choices=(
            "simple_baseline",
            "measured_features",
            "clip",
            "dino",
            "brain",
        ),
    )
    parser.add_argument(
        "--wb-target-mode",
        required=True,
        choices=(
            "absolute_kelvin",
            "delta_from_as_shot",
        ),
    )
    parser.add_argument("--representation-name", required=True)
    parser.add_argument("--representation-version", required=True)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--feature-version", default=None)
    parser.add_argument("--estimator-name", required=True)
    parser.add_argument(
        "--estimator-config",
        type=_json_object,
        default={},
    )
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    manifest = DatasetImportManifest.model_validate_json(
        args.manifest.resolve().read_text(encoding="utf-8")
    )
    split = EventSafeSplitManifest.model_validate_json(
        args.split.resolve().read_text(encoding="utf-8")
    )

    spec = build_candidate_experiment_spec(
        manifest=manifest,
        split=split,
        candidate_name=args.candidate_name,
        candidate_family=args.candidate_family,
        white_balance_target_mode=WhiteBalanceTargetMode(
            args.wb_target_mode
        ),
        representation=RepresentationSpec(
            name=args.representation_name,
            version=args.representation_version,
            model_id=args.model_id,
            feature_version=args.feature_version,
        ),
        estimator=EstimatorSpec(
            name=args.estimator_name,
            config=args.estimator_config,
        ),
        random_seed=args.random_seed,
        code_revision=args.code_revision,
    )

    output = (
        args.output.resolve()
        if args.output
        else Path.cwd().resolve().parent
        / "docs"
        / "runtime"
        / f"phase12_experiment_{spec.candidate_name}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            spec.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=== Phase 12 Candidate Experiment Contract ===")
    print(f"candidate: {spec.candidate_name}")
    print(f"family: {spec.candidate_family}")
    print(f"experiment_id: {spec.experiment_id}")
    print(f"dataset_id: {spec.dataset_id}")
    print(f"split_id: {spec.split_id}")
    print(f"train samples: {spec.train_sample_count}")
    print(f"validation samples: {spec.validation_sample_count}")
    print(f"WB target mode: {spec.white_balance_target_mode.value}")
    print(f"Spec: {output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
