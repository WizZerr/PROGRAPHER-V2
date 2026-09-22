import numpy as np

from app.brain_v2.components import PreprocessedInput, RawInputRecord
from app.brain_v2.contracts import CameraInfo, PreprocessingInfo
from app.brain_v2.features.unified import UnifiedFeatureExtractor
from app.brain_v2.features.visual_regions import RegionEvidence
from app.brain_v2.preprocessing.raw_decode import (
    DecodedRawFrame,
    RawDecodeConfig,
    RawDecodeMetadata,
)


class NoDetectionDetector:
    def detect(self, frame):
        return RegionEvidence(
            state="not_detected",
            detections=(),
            detector_id="validated-test-detector",
            detector_version="1",
        )


def test_unified_features_record_not_detected_state() -> None:
    rgb = np.full((8, 8, 3), 0.2, dtype=np.float32)
    frame = DecodedRawFrame(
        source_path="fake.CR3",
        source_sha256="sha",
        rgb_linear=rgb,
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
    raw = RawInputRecord(
        source_fingerprint="source",
        event_id="event",
        camera=CameraInfo(model="EOS R6"),
        captured_at=None,
        raw_wb=(2.0, 1.0, 1.5, 1.0),
        exif={
            "iso": 100.0,
            "shutter_seconds": 0.01,
            "aperture": 2.8,
            "focal_length_mm": 50.0,
        },
        missing_fields=(),
        raw_path="fake.CR3",
    )
    pre = PreprocessedInput(
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
        decoded_frame=frame,
    )

    result = UnifiedFeatureExtractor(
        region_detector=NoDetectionDetector()
    ).run(pre)

    mapping = dict(zip(result.features.feature_names, result.features.values))
    categorical = dict(result.features.categorical_context)

    assert result.features.version == "brain-v2-features-v1.3"
    assert mapping["region.face.available"] == 1.0
    assert mapping["region.face.detected"] == 0.0
    assert categorical["region.detector_state"] == "not_detected"
