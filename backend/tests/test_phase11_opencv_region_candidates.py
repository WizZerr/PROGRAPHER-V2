from __future__ import annotations

import numpy as np

from app.brain_v2.features.opencv_regions import (
    DETECTOR_ID,
    DETECTOR_VERSION,
    OpenCVEventRegionDetector,
    _linear_to_bgr8,
    _normalized_box,
    _softmax_foreground,
)
from app.brain_v2.features.visual_regions import (
    NormalizedBox,
    RegionDetection,
    RegionKindStatus,
)
from app.brain_v2.preprocessing.raw_decode import (
    DecodedRawFrame,
    RawDecodeConfig,
    RawDecodeMetadata,
)


def _frame() -> DecodedRawFrame:
    return DecodedRawFrame(
        source_path="fake.CR3",
        source_sha256="sha",
        rgb_linear=np.full((8, 8, 3), 0.2, dtype=np.float32),
        metadata=RawDecodeMetadata(
            preprocessing_version="raw-linear-srgb-v1",
            raw_engine="test",
            raw_engine_version="1",
            numpy_version=np.__version__,
            color_space="linear_srgb",
            bit_depth_before_normalization=16,
            normalized_dtype="float32",
            width=8,
            height=8,
            raw_width=8,
            raw_height=8,
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
        ),
    )


def test_linear_to_bgr8_is_finite_uint8() -> None:
    rgb = np.array(
        [[[0.0, 0.18, 1.0], [1.0, 0.0, 0.18]]],
        dtype=np.float32,
    )
    bgr = _linear_to_bgr8(rgb)

    assert bgr.dtype == np.uint8
    assert bgr.shape == rgb.shape
    assert int(bgr.min()) >= 0
    assert int(bgr.max()) <= 255


def test_softmax_foreground_returns_probability_map() -> None:
    output = np.zeros((1, 2, 2, 2), dtype=np.float32)
    output[0, 1, 0, 0] = 4.0

    probability = _softmax_foreground(output)

    assert probability.shape == (2, 2)
    assert probability[0, 0] > 0.9
    assert 0.0 <= float(probability.min()) <= 1.0
    assert 0.0 <= float(probability.max()) <= 1.0


def test_normalized_box_clips_to_image() -> None:
    box = _normalized_box(
        x=-10,
        y=5,
        width=80,
        height=60,
        image_width=100,
        image_height=50,
        confidence=1.2,
    )

    assert box is not None
    box.validate()
    assert box.x == 0.0
    assert box.confidence == 1.0
    assert box.y + box.height <= 1.000001


def test_composite_detector_keeps_skin_unavailable(monkeypatch, tmp_path) -> None:
    detector = OpenCVEventRegionDetector(
        face_model_path=tmp_path / "face.onnx",
        subject_model_path=tmp_path / "subject.onnx",
    )

    face = RegionDetection(
        kind="face",
        box=NormalizedBox(
            x=0.1,
            y=0.1,
            width=0.2,
            height=0.2,
            confidence=0.95,
        ),
        detector_id=DETECTOR_ID,
        detector_version=DETECTOR_VERSION,
    )

    monkeypatch.setattr(
        detector,
        "_detect_faces",
        lambda _bgr: (
            RegionKindStatus(kind="face", state="available"),
            (face,),
        ),
    )
    monkeypatch.setattr(
        detector,
        "_detect_subjects",
        lambda _bgr: (
            RegionKindStatus(kind="subject", state="not_detected"),
            (),
        ),
    )

    evidence = detector.detect(_frame())

    assert evidence.state == "available"
    assert evidence.status_for("face").state == "available"
    assert evidence.status_for("subject").state == "not_detected"
    assert evidence.status_for("skin").state == "unavailable"
