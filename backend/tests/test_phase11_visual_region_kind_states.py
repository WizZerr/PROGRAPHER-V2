from __future__ import annotations

import numpy as np
import pytest

from app.brain_v2.features.visual_regions import (
    NormalizedBox,
    RegionDetection,
    RegionEvidence,
    RegionKindStatus,
    visual_region_features,
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


def test_per_kind_region_state_can_keep_skin_unavailable() -> None:
    evidence = RegionEvidence(
        state="not_detected",
        detections=(),
        detector_id="composite-test",
        detector_version="1",
        kind_statuses=(
            RegionKindStatus(kind="face", state="not_detected"),
            RegionKindStatus(
                kind="skin",
                state="unavailable",
                reason="No validated skin detector.",
            ),
            RegionKindStatus(kind="subject", state="not_detected"),
        ),
    )

    evidence.validate()

    assert evidence.status_for("face").state == "not_detected"
    assert evidence.status_for("skin").state == "unavailable"
    assert evidence.status_for("subject").state == "not_detected"

    names, values = visual_region_features(_frame(), evidence)
    mapping = dict(zip(names, values))

    assert mapping["region.face.available"] == 1.0
    assert mapping["region.face.detected"] == 0.0
    assert mapping["region.skin.available"] == 0.0
    assert mapping["region.skin.detected"] == 0.0
    assert mapping["region.subject.available"] == 1.0
    assert mapping["region.subject.detected"] == 0.0


def test_backward_compatible_state_inference_still_works() -> None:
    evidence = RegionEvidence(
        state="available",
        detections=(
            RegionDetection(
                kind="face",
                box=NormalizedBox(
                    x=0.1,
                    y=0.1,
                    width=0.2,
                    height=0.2,
                    confidence=0.95,
                ),
                detector_id="legacy-test",
                detector_version="1",
            ),
        ),
        detector_id="legacy-test",
        detector_version="1",
    )

    evidence.validate()

    assert evidence.status_for("face").state == "available"
    assert evidence.status_for("skin").state == "not_detected"
    assert evidence.status_for("subject").state == "not_detected"


def test_per_kind_unavailable_rejects_detection_for_same_kind() -> None:
    evidence = RegionEvidence(
        state="available",
        detections=(
            RegionDetection(
                kind="skin",
                box=NormalizedBox(
                    x=0.1,
                    y=0.1,
                    width=0.2,
                    height=0.2,
                    confidence=0.95,
                ),
                detector_id="composite-test",
                detector_version="1",
            ),
        ),
        detector_id="composite-test",
        detector_version="1",
        kind_statuses=(
            RegionKindStatus(
                kind="skin",
                state="unavailable",
                reason="No validated skin detector.",
            ),
        ),
    )

    with pytest.raises(ValueError, match="cannot carry detections"):
        evidence.validate()
