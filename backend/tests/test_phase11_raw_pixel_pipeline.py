import numpy as np
import pytest

from app.brain_v2.components import RawInputRecord
from app.brain_v2.contracts import CameraInfo
from app.brain_v2.factory import create_phase11_raw_pipeline
from app.brain_v2.preprocessing.raw_decode import (
    DecodedRawFrame,
    RawDecodeConfig,
    RawDecodeMetadata,
)
from app.brain_v2.preprocessing.raw_pixels import RawPixelPreprocessor


class FakeRawBackend:
    def decode(
        self,
        raw_path,
        config,
    ) -> DecodedRawFrame:
        rgb = np.full(
            (8, 8, 3),
            0.2,
            dtype=np.float32,
        )
        frame = DecodedRawFrame(
            source_path=str(raw_path),
            source_sha256="sha",
            rgb_linear=rgb,
            metadata=RawDecodeMetadata(
                preprocessing_version="raw-linear-srgb-v1",
                raw_engine="fake",
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
                iso_speed=400.0,
                shutter_seconds=0.005,
                aperture=2.8,
                focal_length_mm=35.0,
                captured_at="2026-09-20T18:00:00",
                rgb_xyz_matrix=tuple(float(i + 1) / 100 for i in range(12)),
                config=RawDecodeConfig(),
            ),
        )
        frame.validate()
        return frame


def raw_record() -> RawInputRecord:
    return RawInputRecord(
        source_fingerprint="source",
        event_id="event",
        camera=CameraInfo(
            make="Sony",
            model="A7 IV",
        ),
        captured_at=None,
        raw_wb=None,
        exif={
            "iso": None,
            "shutter_seconds": None,
            "aperture": None,
            "focal_length_mm": None,
        },
        missing_fields=(
            "raw_wb",
            "iso",
            "shutter_seconds",
            "aperture",
            "focal_length_mm",
            "captured_at",
        ),
        raw_path="fake.ARW",
    )


def test_raw_pixel_preprocessor_requires_path() -> None:
    record = raw_record()
    record = RawInputRecord(
        source_fingerprint=record.source_fingerprint,
        event_id=record.event_id,
        camera=record.camera,
        captured_at=record.captured_at,
        raw_wb=record.raw_wb,
        exif=record.exif,
        missing_fields=record.missing_fields,
        raw_path=None,
    )

    with pytest.raises(ValueError, match="raw_path"):
        RawPixelPreprocessor(
            backend=FakeRawBackend(),
        ).run(record)


def test_raw_preprocessor_recovers_wb_exif_and_capture_time() -> None:
    preprocessed = RawPixelPreprocessor(
        backend=FakeRawBackend(),
    ).run(raw_record())

    assert preprocessed.source.raw_wb == (2.0, 1.0, 1.5, 1.0)
    assert preprocessed.source.exif["iso"] == 400.0
    assert preprocessed.source.exif["shutter_seconds"] == 0.005
    assert preprocessed.source.captured_at == "2026-09-20T18:00:00"
    assert "raw_wb" not in preprocessed.source.missing_fields
    assert "iso" not in preprocessed.source.missing_fields


def test_phase11_pipeline_uses_recovered_source_metadata() -> None:
    result = create_phase11_raw_pipeline(
        raw_backend=FakeRawBackend(),
    ).run(raw_record())

    assert result.brain_input.preprocessing.version == "raw-linear-srgb-v1"
    assert result.brain_input.features.version == "brain-v2-features-v1.1"
    assert result.brain_input.raw_wb == (2.0, 1.0, 1.5, 1.0)
    assert result.brain_input.exif["iso"] == 400.0
    assert "raw_wb" not in result.brain_input.missing_fields
    assert len(result.brain_input.features.values) > 35
    assert result.quality.requires_full_review is True
    assert result.quality.confidence is None
