from pathlib import Path

import numpy as np
import pytest

from app.brain_v2.preprocessing.raw_decode import (
    DecodedRawFrame,
    RawDecodeConfig,
    RawDecodeMetadata,
    deterministic_sample,
)


def metadata() -> RawDecodeMetadata:
    return RawDecodeMetadata(
        preprocessing_version="raw-linear-srgb-v1",
        raw_engine="test",
        raw_engine_version="1",
        numpy_version=np.__version__,
        color_space="linear_srgb",
        bit_depth_before_normalization=16,
        normalized_dtype="float32",
        width=2,
        height=2,
        raw_width=2,
        raw_height=2,
        orientation_flip=0,
        camera_wb=(2.0, 1.0, 1.5, 1.0),
        daylight_wb=None,
        black_levels=(512.0, 512.0, 512.0, 512.0),
        white_level=16383.0,
        config=RawDecodeConfig(),
    )


def test_decode_config_rejects_hidden_auto_brightness() -> None:
    with pytest.raises(ValueError, match="Auto Bright"):
        RawDecodeConfig(
            no_auto_bright=False,
        ).validate()


def test_decoded_frame_requires_float32_rgb_zero_to_one() -> None:
    frame = DecodedRawFrame(
        source_path=str(Path("fake.CR3")),
        source_sha256="abc",
        rgb_linear=np.zeros((2, 2, 3), dtype=np.float32),
        metadata=metadata(),
    )

    frame.validate()


def test_deterministic_sample_is_bounded() -> None:
    rgb = np.zeros((100, 100, 3), dtype=np.float32)
    sample = deterministic_sample(rgb, max_pixels=1000)

    assert sample.shape[0] * sample.shape[1] <= 2500
    assert sample.shape[2] == 3
