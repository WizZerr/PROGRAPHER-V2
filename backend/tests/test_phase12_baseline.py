from __future__ import annotations

import pytest

from app.brain_v2.training.baseline import (
    fit_simple_baseline,
    generate_validation_predictions,
)
from app.brain_v2.training.dataset_manifest import (
    DatasetImportManifest,
    DatasetManifestSample,
)
from app.brain_v2.training.event_split import (
    EventSafeSplitManifest,
    EventSplitAssignment,
    SampleSplitAssignment,
)


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


def _fixture():
    samples = (
        _sample("t1", "event-train-a", 0.0, 4000, -10),
        _sample("t2", "event-train-b", 1.0, 5000, 0),
        _sample("t3", "event-train-c", 2.0, 9000, 20),
        _sample("v1", "event-val", 99.0, 50000, 150),
        _sample("v2", "event-val", -99.0, 2000, -150),
    )

    manifest = DatasetImportManifest(
        dataset_id="d" * 64,
        dataset_root="C:/data",
        sample_count=len(samples),
        training_ready_count=len(samples),
        event_count=4,
        usable_event_ids=(
            "event-train-a",
            "event-train-b",
            "event-train-c",
            "event-val",
        ),
        event_safe_split_ready=True,
        source_readiness_schema_version="phase12-dataset-readiness-v1",
        samples=samples,
    )

    split = EventSafeSplitManifest(
        split_id="s" * 64,
        dataset_id=manifest.dataset_id,
        seed="fixed",
        validation_fraction=0.25,
        train_event_ids=(
            "event-train-a",
            "event-train-b",
            "event-train-c",
        ),
        validation_event_ids=("event-val",),
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
                event_id="event-train-c",
                split="train",
                stable_score_hex="3" * 64,
            ),
            EventSplitAssignment(
                event_id="event-val",
                split="validation",
                stable_score_hex="4" * 64,
            ),
        ),
        sample_assignments=(
            SampleSplitAssignment(
                sample_id="t1",
                event_id="event-train-a",
                split="train",
            ),
            SampleSplitAssignment(
                sample_id="t2",
                event_id="event-train-b",
                split="train",
            ),
            SampleSplitAssignment(
                sample_id="t3",
                event_id="event-train-c",
                split="train",
            ),
            SampleSplitAssignment(
                sample_id="v1",
                event_id="event-val",
                split="validation",
            ),
            SampleSplitAssignment(
                sample_id="v2",
                event_id="event-val",
                split="validation",
            ),
        ),
        train_sample_count=3,
        validation_sample_count=2,
    )
    return manifest, split


def test_median_baseline_uses_train_targets_only() -> None:
    manifest, split = _fixture()

    baseline = fit_simple_baseline(
        manifest=manifest,
        split=split,
        strategy="median",
    )

    assert baseline.fitted_values == {
        "exposure_stops": 1.0,
        "temperature_k": 5000.0,
        "tint": 0.0,
    }


def test_mean_baseline_uses_train_targets_only() -> None:
    manifest, split = _fixture()

    baseline = fit_simple_baseline(
        manifest=manifest,
        split=split,
        strategy="mean",
    )

    assert baseline.fitted_values["exposure_stops"] == pytest.approx(1.0)
    assert baseline.fitted_values["temperature_k"] == pytest.approx(6000.0)
    assert baseline.fitted_values["tint"] == pytest.approx(10.0 / 3.0)


def test_validation_extremes_do_not_change_fitted_baseline() -> None:
    manifest, split = _fixture()

    first = fit_simple_baseline(
        manifest=manifest,
        split=split,
        strategy="median",
    )

    changed_samples = tuple(
        sample.model_copy(
            update={
                "targets": {
                    "exposure_stops": 5.0,
                    "temperature_k": 2000,
                    "tint": -150,
                }
            }
        )
        if sample.event_id == "event-val"
        else sample
        for sample in manifest.samples
    )
    changed_manifest = manifest.model_copy(
        update={"samples": changed_samples}
    )

    second = fit_simple_baseline(
        manifest=changed_manifest,
        split=split,
        strategy="median",
    )

    assert first.fitted_values == second.fitted_values
    assert first.baseline_id == second.baseline_id


def test_predictions_cover_validation_only() -> None:
    manifest, split = _fixture()
    baseline = fit_simple_baseline(
        manifest=manifest,
        split=split,
        strategy="median",
    )

    bundle = generate_validation_predictions(
        manifest=manifest,
        split=split,
        baseline=baseline,
    )

    assert {item.sample_id for item in bundle.predictions} == {
        "v1",
        "v2",
    }
    assert all(
        item.exposure_stops == 1.0
        for item in bundle.predictions
    )


def test_baseline_id_changes_with_strategy() -> None:
    manifest, split = _fixture()

    median = fit_simple_baseline(
        manifest=manifest,
        split=split,
        strategy="median",
    )
    mean = fit_simple_baseline(
        manifest=manifest,
        split=split,
        strategy="mean",
    )

    assert median.baseline_id != mean.baseline_id


def test_dataset_split_mismatch_is_rejected() -> None:
    manifest, split = _fixture()
    bad_split = split.model_copy(
        update={"dataset_id": "x" * 64}
    )

    with pytest.raises(ValueError, match="dataset_id"):
        fit_simple_baseline(
            manifest=manifest,
            split=bad_split,
            strategy="median",
        )
