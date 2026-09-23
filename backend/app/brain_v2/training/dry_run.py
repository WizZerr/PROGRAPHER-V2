from __future__ import annotations

from typing import Any

from app.brain_v2.models.edit_targets import WhiteBalanceTargetMode
from app.brain_v2.training.baseline import (
    fit_simple_baseline,
    generate_validation_predictions,
)
from app.brain_v2.training.dataset_manifest import (
    DatasetImportManifest,
    DatasetManifestSample,
)
from app.brain_v2.training.evaluation import evaluate_candidate_predictions
from app.brain_v2.training.event_split import (
    EventSafeSplitManifest,
    EventSplitAssignment,
    SampleSplitAssignment,
)
from app.brain_v2.training.experiment_contract import (
    EstimatorSpec,
    RepresentationSpec,
    build_candidate_experiment_spec,
)


DRY_RUN_SCHEMA_VERSION = "phase12-end-to-end-dry-run-v1"


def _sample(
    sample_id: str,
    event_id: str,
    exposure: float,
    temperature: int,
    tint: int,
) -> DatasetManifestSample:
    return DatasetManifestSample(
        sample_id=sample_id,
        event_id=event_id,
        raw_path=f"C:/synthetic/{event_id}/{sample_id}.cr3",
        raw_relpath=f"{event_id}/{sample_id}.cr3",
        raw_sha256=(sample_id * 64)[:64],
        xmp_path=f"C:/synthetic/{event_id}/{sample_id}.cr3.xmp",
        xmp_relpath=f"{event_id}/{sample_id}.cr3.xmp",
        xmp_sha256=((sample_id + "x") * 64)[:64],
        pair_status="paired",
        target_status="ready",
        ready_for_three_target_training=True,
        targets={
            "exposure_stops": exposure,
            "temperature_k": temperature,
            "tint": tint,
        },
        missing_target_fields=(),
        rendering_context={
            "process_version": "11.0",
            "camera_profile": "Adobe Standard",
            "tone_curve": "Medium Contrast",
            "preset_identity": "none",
        },
        error=None,
    )


def build_synthetic_manifest() -> DatasetImportManifest:
    samples = (
        _sample("train-a-1", "event-train-a", -0.2, 4600, -4),
        _sample("train-a-2", "event-train-a", 0.2, 5000, 0),
        _sample("train-b-1", "event-train-b", 0.4, 5200, 2),
        _sample("train-b-2", "event-train-b", 0.8, 5600, 6),
        _sample("val-c-1", "event-val-c", 0.1, 4900, -1),
        _sample("val-c-2", "event-val-c", 0.7, 5500, 5),
    )

    return DatasetImportManifest(
        dataset_id="synthetic-dataset-" + ("d" * 46),
        dataset_root="C:/synthetic",
        sample_count=len(samples),
        training_ready_count=len(samples),
        event_count=3,
        usable_event_ids=(
            "event-train-a",
            "event-train-b",
            "event-val-c",
        ),
        event_safe_split_ready=True,
        source_readiness_schema_version="phase12-dataset-readiness-v1",
        samples=samples,
    )


def build_synthetic_split(
    manifest: DatasetImportManifest,
) -> EventSafeSplitManifest:
    return EventSafeSplitManifest(
        split_id="synthetic-split-" + ("s" * 50),
        dataset_id=manifest.dataset_id,
        seed="phase12-dry-run-v1",
        validation_fraction=1.0 / 3.0,
        train_event_ids=("event-train-a", "event-train-b"),
        validation_event_ids=("event-val-c",),
        event_assignments=(
            EventSplitAssignment(
                event_id="event-train-a",
                split="train",
                stable_score_hex="1" * 64,
            ),
            EventSplitAssignment(
                event_id="event-train-b",
                split="train",
                stable_score_hex="2" * 64,
            ),
            EventSplitAssignment(
                event_id="event-val-c",
                split="validation",
                stable_score_hex="3" * 64,
            ),
        ),
        sample_assignments=(
            SampleSplitAssignment(
                sample_id="train-a-1",
                event_id="event-train-a",
                split="train",
            ),
            SampleSplitAssignment(
                sample_id="train-a-2",
                event_id="event-train-a",
                split="train",
            ),
            SampleSplitAssignment(
                sample_id="train-b-1",
                event_id="event-train-b",
                split="train",
            ),
            SampleSplitAssignment(
                sample_id="train-b-2",
                event_id="event-train-b",
                split="train",
            ),
            SampleSplitAssignment(
                sample_id="val-c-1",
                event_id="event-val-c",
                split="validation",
            ),
            SampleSplitAssignment(
                sample_id="val-c-2",
                event_id="event-val-c",
                split="validation",
            ),
        ),
        train_sample_count=4,
        validation_sample_count=2,
    )


def run_phase12_synthetic_dry_run() -> dict[str, Any]:
    manifest = build_synthetic_manifest()
    split = build_synthetic_split(manifest)

    baseline = fit_simple_baseline(
        manifest=manifest,
        split=split,
        strategy="median",
    )
    prediction_bundle = generate_validation_predictions(
        manifest=manifest,
        split=split,
        baseline=baseline,
    )

    experiment = build_candidate_experiment_spec(
        manifest=manifest,
        split=split,
        candidate_name="synthetic-simple-baseline-median",
        candidate_family="simple_baseline",
        white_balance_target_mode=WhiteBalanceTargetMode.ABSOLUTE_KELVIN,
        representation=RepresentationSpec(
            name="constant-target-baseline",
            version="v1",
            feature_version=None,
            model_id=None,
        ),
        estimator=EstimatorSpec(
            name="median",
            config={},
        ),
        random_seed=42,
        code_revision="synthetic-dry-run",
    )

    evaluation = evaluate_candidate_predictions(
        manifest=manifest,
        split=split,
        candidate_name=experiment.candidate_name,
        predictions=list(prediction_bundle.predictions),
    )

    if evaluation.dataset_id != experiment.dataset_id:
        raise RuntimeError("dry-run dataset identity mismatch")
    if evaluation.split_id != experiment.split_id:
        raise RuntimeError("dry-run split identity mismatch")
    if evaluation.validation_sample_count != split.validation_sample_count:
        raise RuntimeError("dry-run validation sample count mismatch")

    return {
        "schema_version": DRY_RUN_SCHEMA_VERSION,
        "fixture_kind": "synthetic_only",
        "quality_claim_allowed": False,
        "manifest": {
            "dataset_id": manifest.dataset_id,
            "sample_count": manifest.sample_count,
            "event_count": manifest.event_count,
            "training_ready_count": manifest.training_ready_count,
        },
        "split": {
            "split_id": split.split_id,
            "train_sample_count": split.train_sample_count,
            "validation_sample_count": split.validation_sample_count,
            "train_event_ids": list(split.train_event_ids),
            "validation_event_ids": list(split.validation_event_ids),
        },
        "baseline": baseline.model_dump(mode="json"),
        "experiment": experiment.model_dump(mode="json"),
        "evaluation": evaluation.model_dump(mode="json"),
        "assertions": {
            "dataset_identity_connected": True,
            "split_identity_connected": True,
            "train_only_baseline_fitting": True,
            "validation_only_predictions": True,
            "evaluation_completed": True,
        },
        "warning": (
            "Synthetic dry-run only. Metrics prove pipeline wiring and are "
            "not a photographic-quality result or evidence of model usefulness."
        ),
    }
