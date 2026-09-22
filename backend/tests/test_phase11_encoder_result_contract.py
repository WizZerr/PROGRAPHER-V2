import pytest

from app.brain_v2.vision_encoders.contracts import EncoderResult


def test_encoder_result_rejects_wrong_dimension() -> None:
    result = EncoderResult(
        encoder_id="candidate",
        encoder_version="1",
        vector=(1.0, 2.0),
        dimension=3,
        device="cpu",
        input_contract="v1",
    )

    with pytest.raises(ValueError, match="dimension"):
        result.validate()
