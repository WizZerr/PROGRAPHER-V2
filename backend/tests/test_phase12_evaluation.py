from __future__ import annotations

import pytest

from app.brain_v2.training.dataset_manifest import (
    DatasetImportManifest,
    DatasetManifestSample,
)
from app.brain_v2.training.evaluation import (
    CandidatePrediction,
    _percentile_linear,
    compare_candidate_to_baseline,
    evaluate_candidate_predictions,
)
from app.brain_v2.training.event_split import (
    EventSafeSplitManifest,
    EventSplitAssignment,
    SampleSplitAssignment,
)


def _sample(sample_id: str, event_id: str, exposure: float):
    return DatasetManifestSample(
        sample_id=sample_id,
        event_id=event_id,
        raw_path=f"C:/data/{event_id}/{sample_id}.cr3",
        raw_relpath=f"{event_id}/{sample_id}.cr3",
        raw_sha256=(sample_id * 64)[:64],
        xmp_path=f"C:/data/{event_id}/{sample_id}.cr3.xmp",
        xmp_relpath=f"{event_id}/{sample_id}.cr3.xmp",
        xmp_sha256=((sample_id + "x") * 64)[:64],
        pair_status="paired",
        target_status="ready",
        ready_for_three_target_training=True,
        targets={
            "exposure_stops": exposure,
            "temperature_k": 5000,
            "tint": 0,
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


def _fixture():
    train = _sample("train-1", "event-train", 0.0)
    val1 = _sample("val-1", "event-val", 0.0)
    val2 = _sample("val-2", "event-val", 1.0)

    manifest = DatasetImportManifest(
        dataset_id="d" * 64,
        dataset_root="C:/data",
        sample_count=3,
        training_ready_count=3,
        event_count=2,
        usable_event_ids=("event-train", "event-val"),
        event_safe_split_ready=True,
        source_readiness_schema_version="phase12-dataset-readiness-v1",
        samples=(train, val1, val2),
    )

    split = EventSafeSplitManifest(
        split_id="s" * 64,
        dataset_id=manifest.dataset_id,
        seed="fixed",
        validation_fraction=0.5,
        train_event_ids=("event-train",),
        validation_event_ids=("event-val",),
        event_assignments=(
            EventSplitAssignment(
                event_id="event-train",
                split="train",
                stable_score_hex="a" * 64,
            ),
            EventSplitAssignment(
                event_id="event-val",
                split="validation",
                stable_score_hex="b" * 64,
            ),
        ),
        sample_assignments=(
            SampleSplitAssignment(
                sample_id="train-1",
                event_id="event-train",
                split="train",
            ),
            SampleSplitAssignment(
                sample_id="val-1",
                event_id="event-val",
                split="validation",
            ),
            SampleSplitAssignment(
                sample_id="val-2",
                event_id="event-val",
                split="validation",
            ),
        ),
        train_sample_count=1,
        validation_sample_count=2,
    )
    return manifest, split


def _pred(sample_id: str, exposure: float, temp: float = 5000, tint: float = 0):
    return CandidatePrediction(
        sample_id=sample_id,
        exposure_stops=exposure,
        temperature_k=temp,
        tint=tint,
    )


def test_evaluates_validation_samples_only() -> None:
    manifest, split = _fixture()

    result = evaluate_candidate_predictions(
        manifest=manifest,
        split=split,
        candidate_name="candidate",
        predictions=[
            _pred("val-1", 0.5),
            _pred("val-2", 0.5),
        ],
    )

    assert result.validation_sample_count == 2
    assert result.metrics["exposure_stops"].mae == pytest.approx(0.5)
    assert result.metrics["temperature_k"].mae == 0.0
    assert result.metrics["tint"].mae == 0.0


def test_missing_prediction_is_rejected() -> None:
    manifest, split = _fixture()

    with pytest.raises(ValueError, match="missing predictions"):
        evaluate_candidate_predictions(
            manifest=manifest,
            split=split,
            candidate_name="candidate",
            predictions=[_pred("val-1", 0.0)],
        )


def test_extra_train_prediction_is_rejected() -> None:
    manifest, split = _fixture()

    with pytest.raises(ValueError, match="unexpected predictions"):
        evaluate_candidate_predictions(
            manifest=manifest,
            split=split,
            candidate_name="candidate",
            predictions=[
                _pred("val-1", 0.0),
                _pred("val-2", 1.0),
                _pred("train-1", 0.0),
            ],
        )


def test_duplicate_prediction_is_rejected() -> None:
    manifest, split = _fixture()

    with pytest.raises(ValueError, match="Duplicate prediction"):
        evaluate_candidate_predictions(
            manifest=manifest,
            split=split,
            candidate_name="candidate",
            predictions=[
                _pred("val-1", 0.0),
                _pred("val-1", 0.0),
                _pred("val-2", 1.0),
            ],
        )


def test_percentile_is_deterministic_linear_interpolation() -> None:
    values = [0.0, 1.0, 2.0, 3.0]
    assert _percentile_linear(values, 0.5) == pytest.approx(1.5)
    assert _percentile_linear(values, 0.9) == pytest.approx(2.7)


def test_baseline_comparison_reports_mae_improvement() -> None:
    manifest, split = _fixture()

    baseline = evaluate_candidate_predictions(
        manifest=manifest,
        split=split,
        candidate_name="baseline",
        predictions=[
            _pred("val-1", 1.0, temp=5100, tint=10),
            _pred("val-2", 2.0, temp=5100, tint=10),
        ],
    )
    candidate = evaluate_candidate_predictions(
        manifest=manifest,
        split=split,
        candidate_name="candidate",
        predictions=[
            _pred("val-1", 0.5, temp=5050, tint=5),
            _pred("val-2", 1.5, temp=5050, tint=5),
        ],
    )

    comparison = compare_candidate_to_baseline(
        candidate=candidate,
        baseline=baseline,
    )

    assert comparison.per_target["exposure_stops"][
        "mae_improvement_percent"
    ] == pytest.approx(50.0)
    assert comparison.per_target["temperature_k"][
        "mae_improvement_percent"
    ] == pytest.approx(50.0)
    assert comparison.per_target["tint"][
        "mae_improvement_percent"
    ] == pytest.approx(50.0)


def test_manifest_split_dataset_mismatch_is_rejected() -> None:
    manifest, split = _fixture()
    bad_split = split.model_copy(
        update={"dataset_id": "x" * 64}
    )

    with pytest.raises(ValueError, match="dataset_id"):
        evaluate_candidate_predictions(
            manifest=manifest,
            split=bad_split,
            candidate_name="candidate",
            predictions=[
                _pred("val-1", 0.0),
                _pred("val-2", 1.0),
            ],
        )
