from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.brain_v2.features.rtdetr_person import (
    DETECTOR_ID,
    DETECTOR_VERSION,
    RTDETRPersonDetector,
    YuNetRTDETRRegionDetector,
    _is_person_label,
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


def test_person_label_filter_is_explicit() -> None:
    assert _is_person_label("person")
    assert _is_person_label(" Person ")
    assert not _is_person_label("dog")
    assert not _is_person_label("sculpture")


def test_missing_model_is_explicitly_unavailable(tmp_path: Path) -> None:
    detector = RTDETRPersonDetector(
        model_path=tmp_path / "missing",
    )

    status, detections = detector.detect_subjects(_frame())

    assert status.state == "unavailable"
    assert status.reason is not None
    assert detections == ()


def test_composite_keeps_skin_unavailable(monkeypatch, tmp_path: Path) -> None:
    detector = YuNetRTDETRRegionDetector(
        face_model_path=tmp_path / "face.onnx",
        person_model_path=tmp_path / "rtdetr",
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
        detector_id="old",
        detector_version="old",
    )

    monkeypatch.setattr(
        detector._yunet,
        "_detect_faces",
        lambda _bgr: (
            RegionKindStatus(kind="face", state="available"),
            (face,),
        ),
    )
    monkeypatch.setattr(
        detector._person,
        "detect_subjects",
        lambda _frame: (
            RegionKindStatus(kind="subject", state="not_detected"),
            (),
        ),
    )

    evidence = detector.detect(_frame())

    assert evidence.status_for("face").state == "available"
    assert evidence.status_for("subject").state == "not_detected"
    assert evidence.status_for("skin").state == "unavailable"
    assert evidence.detections[0].detector_id == DETECTOR_ID
    assert evidence.detections[0].detector_version == DETECTOR_VERSION


def test_invalid_device_fails_as_unavailable(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    detector = RTDETRPersonDetector(
        model_path=model_dir,
        device="bad-device",
    )

    status, detections = detector.detect_subjects(_frame())

    assert status.state == "unavailable"
    assert "Unsupported device" in (status.reason or "")
    assert detections == ()
