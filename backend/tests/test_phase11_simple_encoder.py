from app.brain_v2.contracts import (
    Availability,
    BrainInput,
    CameraInfo,
    FeatureVector,
    PreprocessingInfo,
)
from app.brain_v2.vision_encoders.simple import SimpleMeasuredEncoder


def test_simple_encoder_uses_exact_numeric_feature_vector() -> None:
    brain_input = BrainInput(
        source_fingerprint="source",
        event_id="event",
        camera=CameraInfo(model="EOS R6"),
        captured_at=None,
        raw_wb=(2.0, 1.0, 1.5, 1.0),
        exif={},
        missing_fields=(),
        preprocessing=PreprocessingInfo(
            version="raw-linear-srgb-v1",
            raw_decoder="test",
            color_pipeline="linear_srgb",
        ),
        features=FeatureVector(
            version="brain-v2-features-v1.2",
            values=(1.0, 2.5, -0.25),
            feature_names=("a", "b", "c"),
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

    result = SimpleMeasuredEncoder().encode(brain_input)

    assert result.vector == (1.0, 2.5, -0.25)
    assert result.dimension == 3
    assert result.input_contract == "brain-v2-features-v1.2"
