from __future__ import annotations

from app.brain_v2.components import FeatureExtractionResult, PreprocessedInput
from app.brain_v2.contracts import FeatureVector
from app.brain_v2.features.metadata import MetadataFeatureExtractor
from app.brain_v2.features.pixel_stats import compute_pixel_statistics, pixel_statistics_feature_vector
from app.brain_v2.features.visual_regions import (
    UnavailableVisualRegionDetector,
    VisualRegionDetector,
    visual_region_features,
)

UNIFIED_FEATURE_VERSION = "brain-v2-features-v1.3"


def _normalized_wb(wb: tuple[float, ...] | None) -> tuple[float | None, float | None]:
    if wb is None or len(wb) < 3:
        return None, None

    red = float(wb[0])
    blue = float(wb[2])
    greens = [float(wb[1])]
    if len(wb) >= 4:
        greens.append(float(wb[3]))
    green = sum(greens) / len(greens)

    if green <= 0:
        return None, None

    return red / green, blue / green


class UnifiedFeatureExtractor:
    def __init__(self, *, region_detector: VisualRegionDetector | None = None) -> None:
        self.region_detector = region_detector or UnavailableVisualRegionDetector()

    def run(self, data: PreprocessedInput) -> FeatureExtractionResult:
        if data.decoded_frame is None:
            raise ValueError("UnifiedFeatureExtractor דורש decoded RAW frame.")

        pixel_vector = pixel_statistics_feature_vector(
            compute_pixel_statistics(data.decoded_frame)
        )
        metadata_vector = MetadataFeatureExtractor(
            version="metadata-features-v1"
        ).run(data).features

        names: list[str] = []
        values: list[float] = []

        for name, value in zip(pixel_vector.feature_names, pixel_vector.values):
            names.append(f"pixel.{name}")
            values.append(float(value))

        for name, value in zip(metadata_vector.feature_names, metadata_vector.values):
            names.append(f"exif.{name}")
            values.append(float(value))

        wb = data.source.raw_wb or data.decoded_frame.metadata.camera_wb
        r_over_g, b_over_g = _normalized_wb(wb)

        names.extend((
            "wb.red_over_green",
            "wb.red_over_green__missing",
            "wb.blue_over_green",
            "wb.blue_over_green__missing",
        ))
        if r_over_g is None or b_over_g is None:
            values.extend((0.0, 1.0, 0.0, 1.0))
        else:
            values.extend((float(r_over_g), 0.0, float(b_over_g), 0.0))

        matrix = data.decoded_frame.metadata.rgb_xyz_matrix
        for index in range(12):
            names.append(f"camera.rgb_xyz_{index:02d}")
            values.append(0.0 if matrix is None else float(matrix[index]))
        names.append("camera.rgb_xyz__missing")
        values.append(1.0 if matrix is None else 0.0)

        evidence = self.region_detector.detect(data.decoded_frame)
        region_names, region_values = visual_region_features(
            data.decoded_frame,
            evidence,
        )
        names.extend(region_names)
        values.extend(region_values)

        categorical: list[tuple[str, str]] = []
        if data.source.camera.make:
            categorical.append(("camera.make", data.source.camera.make))
        if data.source.camera.model:
            categorical.append(("camera.model", data.source.camera.model))

        categorical.append(("region.detector_state", evidence.state))
        if evidence.detector_id:
            categorical.append(("region.detector_id", evidence.detector_id))
        if evidence.detector_version:
            categorical.append(("region.detector_version", evidence.detector_version))

        vector = FeatureVector(
            version=UNIFIED_FEATURE_VERSION,
            values=tuple(values),
            feature_names=tuple(names),
            categorical_context=tuple(categorical),
        )
        vector.validate()
        return FeatureExtractionResult(preprocessed=data, features=vector)
