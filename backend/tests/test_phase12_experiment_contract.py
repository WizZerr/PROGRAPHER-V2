from __future__ import annotations

import pytest

from app.brain_v2.models.edit_targets import WhiteBalanceTargetMode
from app.brain_v2.training.dataset_manifest import (
    DatasetImportManifest,
    DatasetManifestSample,
)
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


def _sample(sample_id: str, event_id: str):
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
            "exposure_stops": 0.1,
            "temperature_k": 5200,
            "tint": 2,
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
        _sample("t1", "event-train"),
        _sample("v1", "event-val"),
    )
    manifest = DatasetImportManifest(
        dataset_id="d" * 64,
        dataset_root="C:/data",
        sample_count=2,
        training_ready_count=2,
        event_count=2,
        usable_event_ids=("event-train", "event-val"),
        event_safe_split_ready=True,
        source_readiness_schema_version="phase12-dataset-readiness-v1",
        samples=samples,
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
                sample_id="t1",
                event_id="event-train",
                split="train",
            ),
            SampleSplitAssignment(
                sample_id="v1",
                event_id="event-val",
                split="validation",
            ),
        ),
        train_sample_count=1,
        validation_sample_count=1,
    )
    return manifest, split


def _build(**overrides):
    manifest, split = _fixture()
    values = {
        "manifest": manifest,
        "split": split,
        "candidate_name": "dino-extra-trees",
        "candidate_family": "dino",
        "white_balance_target_mode": WhiteBalanceTargetMode.ABSOLUTE_KELVIN,
        "representation": RepresentationSpec(
            name="dinov3",
            version="vits16-lvd1689m",
            model_id="facebook/dinov3-vits16-pretrain-lvd1689m",
            feature_version="brain-v2-features-v1.3",
        ),
        "estimator": EstimatorSpec(
            name="extra_trees",
            config={
                "n_estimators": 256,
                "max_depth": None,
            },
        ),
        "random_seed": 42,
        "code_revision": "git:abc123",
    }
    values.update(overrides)
    return build_candidate_experiment_spec(**values)


def test_same_inputs_produce_same_experiment_id() -> None:
    first = _build()
    second = _build()

    assert first.experiment_id == second.experiment_id
    assert first.train_cohort_sha256 == second.train_cohort_sha256
    assert first.validation_cohort_sha256 == second.validation_cohort_sha256


def test_representation_change_changes_experiment_id() -> None:
    first = _build()
    second = _build(
        representation=RepresentationSpec(
            name="dinov3",
            version="different",
            model_id="facebook/dinov3-vits16-pretrain-lvd1689m",
            feature_version="brain-v2-features-v1.3",
        )
    )

    assert first.experiment_id != second.experiment_id


def test_wb_target_mode_is_part_of_experiment_identity() -> None:
    first = _build()
    second = _build(
        white_balance_target_mode=WhiteBalanceTargetMode.DELTA_FROM_AS_SHOT
    )

    assert first.experiment_id != second.experiment_id


def test_estimator_config_key_order_does_not_change_identity() -> None:
    first = _build(
        estimator=EstimatorSpec(
            name="extra_trees",
            config={"a": 1, "b": 2},
        )
    )
    second = _build(
        estimator=EstimatorSpec(
            name="extra_trees",
            config={"b": 2, "a": 1},
        )
    )

    assert first.experiment_id == second.experiment_id


def test_dataset_split_mismatch_is_rejected() -> None:
    manifest, split = _fixture()
    bad_split = split.model_copy(
        update={"dataset_id": "x" * 64}
    )

    with pytest.raises(ValueError, match="dataset_id"):
        build_candidate_experiment_spec(
            manifest=manifest,
            split=bad_split,
            candidate_name="measured",
            candidate_family="measured_features",
            white_balance_target_mode=WhiteBalanceTargetMode.ABSOLUTE_KELVIN,
            representation=RepresentationSpec(
                name="measured",
                version="v1",
            ),
            estimator=EstimatorSpec(
                name="extra_trees",
                config={},
            ),
            random_seed=42,
            code_revision="git:abc",
        )


def test_blank_code_revision_is_rejected() -> None:
    with pytest.raises(ValueError, match="code_revision"):
        _build(code_revision="   ")


def test_candidate_family_is_recorded_explicitly() -> None:
    spec = _build(
        candidate_name="measured",
        candidate_family="measured_features",
        representation=RepresentationSpec(
            name="measured-features",
            version="v1.3",
            feature_version="brain-v2-features-v1.3",
        ),
    )

    assert spec.candidate_family == "measured_features"
    assert spec.representation.feature_version == "brain-v2-features-v1.3"
