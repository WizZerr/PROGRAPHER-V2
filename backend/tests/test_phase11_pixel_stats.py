import numpy as np

from app.brain_v2.features.pixel_stats import (
    PIXEL_FEATURE_VERSION,
    compute_pixel_statistics,
    pixel_statistics_feature_vector,
)
from app.brain_v2.preprocessing.raw_decode import (
    DecodedRawFrame,
    RawDecodeConfig,
    RawDecodeMetadata,
)


def frame(rgb: np.ndarray) -> DecodedRawFrame:
    metadata = RawDecodeMetadata(
        preprocessing_version="raw-linear-srgb-v1",
        raw_engine="test",
        raw_engine_version="1",
        numpy_version=np.__version__,
        color_space="linear_srgb",
        bit_depth_before_normalization=16,
        normalized_dtype="float32",
        width=rgb.shape[1],
        height=rgb.shape[0],
        raw_width=rgb.shape[1],
        raw_height=rgb.shape[0],
        orientation_flip=0,
        camera_wb=None,
        daylight_wb=None,
        black_levels=None,
        white_level=None,
        iso_speed=None,
        shutter_seconds=None,
        aperture=None,
        focal_length_mm=None,
        captured_at=None,
        rgb_xyz_matrix=None,
        config=RawDecodeConfig(),
    )
    result = DecodedRawFrame(
        source_path="fake.CR3",
        source_sha256="abc",
        rgb_linear=rgb.astype(np.float32),
        metadata=metadata,
    )
    result.validate()
    return result


def test_black_image_reports_shadow_clip_not_highlight_clip() -> None:
    stats = compute_pixel_statistics(
        frame(np.zeros((4, 4, 3), dtype=np.float32))
    )

    assert stats.luminance_mean == 0.0
    assert stats.shadow_clip_fraction == 1.0
    assert stats.highlight_clip_fraction == 0.0


def test_white_image_reports_highlight_clip() -> None:
    stats = compute_pixel_statistics(
        frame(np.ones((4, 4, 3), dtype=np.float32))
    )

    assert stats.highlight_clip_fraction == 1.0
    assert stats.shadow_clip_fraction == 0.0


def test_pixel_feature_vector_has_stable_version_and_no_sample_count() -> None:
    stats = compute_pixel_statistics(
        frame(np.full((4, 4, 3), 0.5, dtype=np.float32))
    )
    vector = pixel_statistics_feature_vector(stats)

    assert vector.version == PIXEL_FEATURE_VERSION
    assert "sampled_pixels" not in vector.feature_names
    assert len(vector.values) == len(vector.feature_names)
