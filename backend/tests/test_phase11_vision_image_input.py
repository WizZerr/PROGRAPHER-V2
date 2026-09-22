import numpy as np
import pytest

from app.brain_v2.vision_encoders.image_input import linear_to_encoded_srgb


def test_linear_srgb_conversion_preserves_bounds() -> None:
    rgb = np.array(
        [[[0.0, 0.0031308, 1.0]]],
        dtype=np.float32,
    )

    encoded = linear_to_encoded_srgb(rgb)

    assert encoded.dtype == np.float32
    assert float(encoded.min()) >= 0.0
    assert float(encoded.max()) <= 1.0
    assert encoded[0, 0, 0] == pytest.approx(0.0, abs=1e-7)
    assert encoded[0, 0, 2] == pytest.approx(1.0, abs=1e-6)


def test_linear_mid_gray_is_encoded_before_vision_model_input() -> None:
    rgb = np.full(
        (1, 1, 3),
        0.18,
        dtype=np.float32,
    )

    encoded = linear_to_encoded_srgb(rgb)

    assert 0.45 < float(encoded[0, 0, 0]) < 0.47
