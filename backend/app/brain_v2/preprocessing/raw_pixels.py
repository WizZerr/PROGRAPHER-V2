from __future__ import annotations

from dataclasses import replace

from app.brain_v2.components import PreprocessedInput, RawInputRecord
from app.brain_v2.contracts import PreprocessingInfo
from app.brain_v2.preprocessing.exiftool_metadata import (
    CameraMetadataProvider,
    ExifToolMetadataProvider,
    enrich_raw_input_with_camera_metadata,
)
from app.brain_v2.preprocessing.raw_decode import (
    RawDecodeConfig,
    RawDecoderBackend,
    decode_raw,
)


class RawPixelPreprocessor:
    def __init__(
        self,
        *,
        backend: RawDecoderBackend | None = None,
        config: RawDecodeConfig | None = None,
        camera_metadata_provider: CameraMetadataProvider | None = None,
    ) -> None:
        self.backend = backend
        self.config = config or RawDecodeConfig()
        self.camera_metadata_provider = (
            camera_metadata_provider or ExifToolMetadataProvider()
        )

    def run(self, raw: RawInputRecord) -> PreprocessedInput:
        if not raw.raw_path:
            raise ValueError(
                "RawPixelPreprocessor דורש raw_path מפורש."
            )

        camera_metadata = self.camera_metadata_provider.read(raw.raw_path)
        effective_raw = enrich_raw_input_with_camera_metadata(
            raw,
            camera_metadata,
        )

        frame = decode_raw(
            raw.raw_path,
            backend=self.backend,
            config=self.config,
        )

        fallback = {
            "iso": frame.metadata.iso_speed,
            "shutter_seconds": frame.metadata.shutter_seconds,
            "aperture": frame.metadata.aperture,
            "focal_length_mm": frame.metadata.focal_length_mm,
        }

        effective_exif = dict(effective_raw.exif)
        recovered_fields: set[str] = set()

        for key, fallback_value in fallback.items():
            current = effective_exif.get(key)

            if isinstance(current, (int, float)):
                continue

            if fallback_value is not None:
                effective_exif[key] = fallback_value
                recovered_fields.add(key)

        effective_wb = effective_raw.raw_wb
        if effective_wb is None and frame.metadata.camera_wb is not None:
            effective_wb = frame.metadata.camera_wb
            recovered_fields.add("raw_wb")

        effective_captured_at = effective_raw.captured_at
        if (
            effective_captured_at is None
            and frame.metadata.captured_at is not None
        ):
            effective_captured_at = frame.metadata.captured_at
            recovered_fields.add("captured_at")

        effective_missing = tuple(
            field
            for field in effective_raw.missing_fields
            if field not in recovered_fields
        )

        effective_source = replace(
            effective_raw,
            captured_at=effective_captured_at,
            raw_wb=effective_wb,
            exif=effective_exif,
            missing_fields=effective_missing,
        )

        numeric: dict[str, float] = {}
        for key in (
            "iso",
            "shutter_seconds",
            "aperture",
            "focal_length_mm",
        ):
            value = effective_exif.get(key)
            if isinstance(value, (int, float)):
                numeric[key] = float(value)

        preprocessing = PreprocessingInfo(
            version=frame.metadata.preprocessing_version,
            raw_decoder=(
                f"{frame.metadata.raw_engine}@"
                f"{frame.metadata.raw_engine_version}"
            ),
            color_pipeline=frame.metadata.color_space,
            preview_max_edge_px=None,
        )
        preprocessing.validate()

        return PreprocessedInput(
            source=effective_source,
            preprocessing=preprocessing,
            numeric_metadata=numeric,
            decoded_frame=frame,
        )
