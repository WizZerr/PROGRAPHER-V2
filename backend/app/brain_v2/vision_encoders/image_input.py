from __future__ import annotations

import numpy as np

from app.brain_v2.preprocessing.raw_decode import DecodedRawFrame


VISION_IMAGE_INPUT_VERSION = "linear-srgb-to-encoded-srgb-v1"


def linear_to_encoded_srgb(rgb_linear: np.ndarray) -> np.ndarray:
    if rgb_linear.ndim != 3 or rgb_linear.shape[2] != 3:
        raise ValueError("Vision input חייב HxWx3 RGB.")

    values = np.clip(
        rgb_linear.astype(np.float32, copy=False),
        0.0,
        1.0,
    )

    encoded = np.where(
        values <= 0.0031308,
        values * 12.92,
        1.055 * np.power(values, 1.0 / 2.4) - 0.055,
    )

    return np.clip(encoded, 0.0, 1.0).astype(
        np.float32,
        copy=False,
    )


def frame_to_srgb_uint8(frame: DecodedRawFrame) -> np.ndarray:
    frame.validate()
    encoded = linear_to_encoded_srgb(frame.rgb_linear)
    return np.rint(encoded * 255.0).astype(np.uint8)
