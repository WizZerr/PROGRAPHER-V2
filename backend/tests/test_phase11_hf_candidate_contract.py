import pytest

from app.brain_v2.vision_encoders.hf_candidate import HuggingFaceVisionEncoder
from app.brain_v2.vision_encoders.registry import (
    CLIP_VIT_B32_ID,
    SIMPLE_MEASURED_ID,
)


def test_hf_adapter_rejects_measured_candidate() -> None:
    with pytest.raises(ValueError):
        HuggingFaceVisionEncoder(
            encoder_id=SIMPLE_MEASURED_ID,
        )


def test_hf_adapter_accepts_clip_without_downloading_on_construction() -> None:
    encoder = HuggingFaceVisionEncoder(
        encoder_id=CLIP_VIT_B32_ID,
        device="cpu",
    )

    assert encoder.descriptor.family == "clip"
    assert encoder._model is None
    assert encoder._processor is None
