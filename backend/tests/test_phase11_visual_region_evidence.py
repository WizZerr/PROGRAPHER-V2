import numpy as np
import pytest

from app.brain_v2.features.visual_regions import (
    NormalizedBox,
    RegionDetection,
    RegionEvidence,
    UnavailableVisualRegionDetector,
    visual_region_features,
)
from app.brain_v2.preprocessing.raw_decode import (
    DecodedRawFrame,
    RawDecodeConfig,
    RawDecodeMetadata,
)


def make_frame() -> DecodedRawFrame:
    rgb = np.full((100, 100, 3), 0.20, dtype=np.float32)
    rgb[20:60, 20:60, :] = np.array([0.50, 0.35, 0.30], dtype=np.float32)

    meta = RawDecodeMetadata(
        preprocessing_version="raw-linear-srgb-v1",
        raw_engine="test",
        raw_engine_version="1",
        numpy_version=np.__version__,
        color_space="linear_srgb",
        bit_depth_before_normalization=16,
        normalized_dtype="float32",
        width=100,
        height=100,
        raw_width=100,
        raw_height=100,
        orientation_flip=0,
        camera_wb=(2.0, 1.0, 1.5, 1.0),
        daylight_wb=None,
        black_levels=None,
        white_level=None,
        iso_speed=100.0,
        shutter_seconds=0.01,
        aperture=2.8,
        focal_length_mm=50.0,
        captured_at=None,
        rgb_xyz_matrix=None,
        config=RawDecodeConfig(),
    )
    frame = DecodedRawFrame(
        source_path="fake.CR3",
        source_sha256="sha",
        rgb_linear=rgb,
        metadata=meta,
    )
    frame.validate()
    return frame


def test_unavailable_detector_is_explicit() -> None:
    evidence = UnavailableVisualRegionDetector().detect(make_frame())
    assert evidence.state == "unavailable"
    assert evidence.detections == ()
    assert evidence.reason


def test_not_detected_is_distinct_from_unavailable() -> None:
    evidence = RegionEvidence(
        state="not_detected",
        detections=(),
        detector_id="test-detector",
        detector_version="1",
    )
    names, values = visual_region_features(make_frame(), evidence)
    mapping = dict(zip(names, values))
    assert mapping["region.face.available"] == 1.0
    assert mapping["region.face.detected"] == 0.0


def test_detected_face_produces_measurements() -> None:
    evidence = RegionEvidence(
        state="available",
        detections=(
            RegionDetection(
                kind="face",
                box=NormalizedBox(
                    x=0.20,
                    y=0.20,
                    width=0.40,
                    height=0.40,
                    confidence=0.95,
                ),
                detector_id="test-detector",
                detector_version="1",
            ),
        ),
        detector_id="test-detector",
        detector_version="1",
    )
    names, values = visual_region_features(make_frame(), evidence)
    mapping = dict(zip(names, values))
    assert mapping["region.face.detected"] == 1.0
    assert mapping["region.face.count"] == 1.0
    assert mapping["region.face.max_confidence"] == pytest.approx(0.95)
    assert mapping["region.face.luminance_mean"] > 0.30


def test_invalid_box_is_rejected() -> None:
    with pytest.raises(ValueError):
        NormalizedBox(
            x=0.9,
            y=0.1,
            width=0.2,
            height=0.2,
            confidence=0.9,
        ).validate()
