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
from app.brain_v2.pipeline_contract import (
    InferenceRequest,
    TrainingExample,
    validate_training_inference_contract,
)


def make_input(feature_version: str) -> BrainInput:
    return BrainInput(
        source_fingerprint="source",
        event_id="event",
        camera=CameraInfo(model="Sony A7 IV"),
        captured_at=None,
        raw_wb=(2.0, 1.0, 1.4, 1.0),
        exif={},
        missing_fields=(),
        preprocessing=PreprocessingInfo(
            version="pre-v1",
            raw_decoder="rawpy",
            color_pipeline="linear-v1",
        ),
        features=FeatureVector(
            version=feature_version,
            values=(1.0,),
            feature_names=("f1",),
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


def make_recipe() -> EditRecipe:
    return EditRecipe(
        exposure_stops=0.0,
        temperature_kelvin=5000,
        tint_units=0,
        blacks_units=-40.0,
        process_family="modern",
        process_version="11.0",
        camera_profile="Adobe Standard",
        origin=PredictionOrigin(
            kind="manual",
            candidate_id="ground-truth",
            candidate_version="1",
        ),
        scene_context_applied=False,
        critic_checked=False,
    )


def make_artifact(feature_version: str) -> ArtifactContract:
    return ArtifactContract(
        artifact_id="artifact",
        candidate_id="brain-v2-candidate-001",
        candidate_version="1",
        parent_candidate_id="baseline.train_median.v1",
        brain_contract_version="2.0.0",
        preprocessing_version="pre-v1",
        feature_version=feature_version,
        dataset_manifest_id="dataset-1",
        software_version="0.1.0",
    )


def test_training_and_inference_share_same_contract() -> None:
    brain_input = make_input("features-v1")

    validate_training_inference_contract(
        training_example=TrainingExample(
            brain_input=brain_input,
            target_recipe=make_recipe(),
            dataset_manifest_id="dataset-1",
        ),
        inference_request=InferenceRequest(
            brain_input=brain_input,
            artifact=make_artifact("features-v1"),
        ),
    )


def test_training_inference_feature_version_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="Feature version"):
        validate_training_inference_contract(
            training_example=TrainingExample(
                brain_input=make_input("features-v1"),
                target_recipe=make_recipe(),
                dataset_manifest_id="dataset-1",
            ),
            inference_request=InferenceRequest(
                brain_input=make_input("features-v2"),
                artifact=make_artifact("features-v2"),
            ),
        )
