import pytest

from app.brain_v2.contracts import (
    ArtifactContract,
    Availability,
    BrainInput,
    CameraInfo,
    EditRecipe,
    FeatureVector,
    PredictionOrigin,
    PreprocessingInfo,
)


def make_input(
    *,
    feature_version: str = "features-v1",
    preprocessing_version: str = "pre-v1",
) -> BrainInput:
    return BrainInput(
        source_fingerprint="raw-fingerprint",
        event_id="event-1",
        camera=CameraInfo(
            make="Canon",
            model="EOS R6",
        ),
        captured_at="2026-09-20T18:00:00",
        raw_wb=(2.0, 1.0, 1.5, 1.0),
        exif={
            "iso": 800,
            "shutter_seconds": 0.01,
            "aperture": 2.8,
        },
        missing_fields=(),
        preprocessing=PreprocessingInfo(
            version=preprocessing_version,
            raw_decoder="rawpy/libraw",
            color_pipeline="linear-camera-rgb-v1",
            preview_max_edge_px=2048,
        ),
        features=FeatureVector(
            version=feature_version,
            values=(0.1, 0.2),
            feature_names=("brightness", "contrast"),
        ),
        scene_context=Availability(
            state="not_available",
            reason="Scene Engine not implemented in first Brain V2 path.",
        ),
        critic=Availability(
            state="not_available",
            reason="Critic not implemented in first Brain V2 path.",
        ),
    )


def test_brain_input_roundtrip_preserves_contract() -> None:
    original = make_input()
    restored = BrainInput.from_dict(original.to_dict())

    assert restored == original


def test_missing_camera_and_raw_wb_must_be_explicit() -> None:
    brain_input = BrainInput(
        source_fingerprint="abc",
        event_id="event",
        camera=CameraInfo(),
        captured_at=None,
        raw_wb=None,
        exif={},
        missing_fields=("raw_wb",),
        preprocessing=PreprocessingInfo(
            version="pre-v1",
            raw_decoder="rawpy",
            color_pipeline="linear-v1",
        ),
        features=FeatureVector(
            version="features-v1",
            values=(),
            feature_names=(),
        ),
        scene_context=Availability(
            state="not_available",
            reason="not built",
        ),
        critic=Availability(
            state="not_available",
            reason="not built",
        ),
    )

    with pytest.raises(ValueError, match="Camera model"):
        brain_input.validate()


def test_unavailable_component_requires_reason() -> None:
    with pytest.raises(ValueError):
        Availability(
            state="not_available",
            reason=None,
        ).validate()


def test_edit_recipe_roundtrip_preserves_units_and_origin() -> None:
    recipe = EditRecipe(
        exposure_stops=0.35,
        temperature_kelvin=5650,
        tint_units=-7,
        blacks_units=-40,
        process_family="modern",
        process_version="11.0",
        camera_profile="Adobe Standard",
        origin=PredictionOrigin(
            kind="base_model",
            candidate_id="brain-v2-candidate-001",
            candidate_version="1",
            parent_candidate_id="baseline.train_median.v1",
        ),
        scene_context_applied=False,
        critic_checked=False,
    )

    restored = EditRecipe.from_dict(recipe.to_dict())

    assert restored == recipe
    assert restored.exposure_stops == 0.35
    assert restored.temperature_kelvin == 5650
    assert restored.tint_units == -7


def test_artifact_rejects_feature_version_mismatch() -> None:
    brain_input = make_input(feature_version="features-v2")

    artifact = ArtifactContract(
        artifact_id="artifact-1",
        candidate_id="brain-v2-candidate-001",
        candidate_version="1",
        parent_candidate_id="baseline.train_median.v1",
        brain_contract_version="2.0.0",
        preprocessing_version="pre-v1",
        feature_version="features-v1",
        dataset_manifest_id="dataset-1",
        software_version="0.1.0",
    )

    with pytest.raises(ValueError, match="Features"):
        artifact.validate_for_input(brain_input)
