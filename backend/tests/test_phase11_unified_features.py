import numpy as np

from app.brain_v2.components import (
    PreprocessedInput,
    RawInputRecord,
)
from app.brain_v2.contracts import (
    CameraInfo,
    PreprocessingInfo,
)
from app.brain_v2.features.unified import (
    UNIFIED_FEATURE_VERSION,
    UnifiedFeatureExtractor,
)
from app.brain_v2.preprocessing.raw_decode import (
    DecodedRawFrame,
    RawDecodeConfig,
    RawDecodeMetadata,
)


MATRIX = tuple(float(i + 1) / 100 for i in range(12))


def make_frame(
    *,
    camera_wb=(1849.0, 1024.0, 1678.0, 1024.0),
    matrix=MATRIX,
) -> DecodedRawFrame:
    rgb = np.full(
        (4, 4, 3),
        (0.10, 0.08, 0.07),
        dtype=np.float32,
    )

    metadata = RawDecodeMetadata(
        preprocessing_version="raw-linear-srgb-v1",
        raw_engine="test",
        raw_engine_version="1",
        numpy_version=np.__version__,
        color_space="linear_srgb",
        bit_depth_before_normalization=16,
        normalized_dtype="float32",
        width=4,
        height=4,
        raw_width=4,
        raw_height=4,
        orientation_flip=0,
        camera_wb=camera_wb,
        daylight_wb=None,
        black_levels=None,
        white_level=None,
        iso_speed=100.0,
        shutter_seconds=0.01,
        aperture=2.8,
        focal_length_mm=50.0,
        captured_at=None,
        rgb_xyz_matrix=matrix,
        config=RawDecodeConfig(),
    )

    frame = DecodedRawFrame(
        source_path="fake.CR3",
        source_sha256="sha",
        rgb_linear=rgb,
        metadata=metadata,
    )
    frame.validate()
    return frame


def make_preprocessed(
    *,
    camera_wb=(1849.0, 1024.0, 1678.0, 1024.0),
    matrix=MATRIX,
) -> PreprocessedInput:
    raw = RawInputRecord(
        source_fingerprint="fingerprint",
        event_id="event",
        camera=CameraInfo(
            make="Canon",
            model="EOS R6",
        ),
        captured_at=None,
        raw_wb=camera_wb,
        exif={
            "iso": 100,
            "shutter_seconds": 0.01,
            "aperture": 2.8,
            "focal_length_mm": 50.0,
        },
        missing_fields=(),
        raw_path="fake.CR3",
    )

    return PreprocessedInput(
        source=raw,
        preprocessing=PreprocessingInfo(
            version="raw-linear-srgb-v1",
            raw_decoder="test@1",
            color_pipeline="linear_srgb",
        ),
        numeric_metadata={
            "iso": 100.0,
            "shutter_seconds": 0.01,
            "aperture": 2.8,
            "focal_length_mm": 50.0,
        },
        decoded_frame=make_frame(
            camera_wb=camera_wb,
            matrix=matrix,
        ),
    )


def test_unified_vector_contains_pixel_exif_wb_and_camera_context() -> None:
    result = UnifiedFeatureExtractor().run(
        make_preprocessed()
    )
    vector = result.features
    mapping = dict(zip(vector.feature_names, vector.values))

    assert vector.version == UNIFIED_FEATURE_VERSION
    assert "pixel.luminance_mean" in mapping
    assert mapping["exif.iso"] == 100.0
    assert mapping["exif.iso__missing"] == 0.0
    assert mapping["wb.red_over_green"] > 1.0
    assert mapping["wb.red_over_green__missing"] == 0.0
    assert mapping["camera.rgb_xyz__missing"] == 0.0
    assert mapping["camera.rgb_xyz_00"] == MATRIX[0]
    assert dict(vector.categorical_context) == {
        "camera.make": "Canon",
        "camera.model": "EOS R6",
    }


def test_missing_wb_and_matrix_are_explicit_not_fake_zero() -> None:
    result = UnifiedFeatureExtractor().run(
        make_preprocessed(
            camera_wb=None,
            matrix=None,
        )
    )
    mapping = dict(
        zip(
            result.features.feature_names,
            result.features.values,
        )
    )

    assert mapping["wb.red_over_green"] == 0.0
    assert mapping["wb.red_over_green__missing"] == 1.0
    assert mapping["wb.blue_over_green__missing"] == 1.0
    assert mapping["camera.rgb_xyz_00"] == 0.0
    assert mapping["camera.rgb_xyz__missing"] == 1.0
