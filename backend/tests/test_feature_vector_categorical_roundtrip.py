from app.brain_v2.contracts import (
    Availability,
    BrainInput,
    CameraInfo,
    FeatureVector,
    PreprocessingInfo,
)


def test_categorical_feature_context_survives_brain_input_roundtrip() -> None:
    original = BrainInput(
        source_fingerprint="source",
        event_id="event",
        camera=CameraInfo(
            make="Canon",
            model="EOS R6",
        ),
        captured_at=None,
        raw_wb=(2.0, 1.0, 1.5, 1.0),
        exif={},
        missing_fields=(),
        preprocessing=PreprocessingInfo(
            version="raw-linear-srgb-v1",
            raw_decoder="rawpy/libraw",
            color_pipeline="linear_srgb",
        ),
        features=FeatureVector(
            version="brain-v2-features-v1",
            values=(1.0,),
            feature_names=("test",),
            categorical_context=(
                ("camera.make", "Canon"),
                ("camera.model", "EOS R6"),
            ),
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

    restored = BrainInput.from_dict(original.to_dict())

    assert restored == original
    assert dict(restored.features.categorical_context)["camera.model"] == "EOS R6"
