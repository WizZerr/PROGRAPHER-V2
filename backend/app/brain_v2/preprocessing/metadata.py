from __future__ import annotations

from app.brain_v2.components import PreprocessedInput, RawInputRecord
from app.brain_v2.contracts import PreprocessingInfo


class MetadataPreprocessor:
    """
    First contract implementation.

    It does not decode pixels yet. It only normalizes numeric metadata into a
    stable boundary so future RAW decoding can replace this component without
    changing model/adaptor interfaces.
    """

    def __init__(
        self,
        *,
        version: str = "metadata-pre-v1",
    ) -> None:
        self.version = version

    def run(self, raw: RawInputRecord) -> PreprocessedInput:
        numeric: dict[str, float] = {}

        for key in (
            "iso",
            "shutter_seconds",
            "aperture",
            "focal_length_mm",
        ):
            value = raw.exif.get(key)
            if isinstance(value, (int, float)):
                numeric[key] = float(value)

        preprocessing = PreprocessingInfo(
            version=self.version,
            raw_decoder="not_used_metadata_only",
            color_pipeline="not_available_no_pixel_decode",
            preview_max_edge_px=None,
        )
        preprocessing.validate()

        return PreprocessedInput(
            source=raw,
            preprocessing=preprocessing,
            numeric_metadata=numeric,
        )
