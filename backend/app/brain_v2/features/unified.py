from __future__ import annotations

from app.brain_v2.components import (
    FeatureExtractionResult,
    PreprocessedInput,
)
from app.brain_v2.contracts import FeatureVector
from app.brain_v2.features.metadata import MetadataFeatureExtractor
from app.brain_v2.features.pixel_stats import (
    compute_pixel_statistics,
    pixel_statistics_feature_vector,
)


UNIFIED_FEATURE_VERSION = "brain-v2-features-v1.1"


def _normalized_wb(
    wb: tuple[float, ...] | None,
) -> tuple[float | None, float | None]:
    if wb is None or len(wb) < 3:
        return None, None

    red = float(wb[0])
    green_1 = float(wb[1])
    blue = float(wb[2])

    green_values = [green_1]
    if len(wb) >= 4:
        green_values.append(float(wb[3]))

    green = sum(green_values) / len(green_values)

    if green <= 0:
        return None, None

    return red / green, blue / green


class UnifiedFeatureExtractor:
    """
    Phase 11 unified feature contract.

    Numeric groups:
    - decoded RAW pixel statistics;
    - EXIF numeric values + explicit missing flags;
    - normalized RAW WB ratios + explicit missing flags;
    - camera RGB->XYZ matrix from LibRaw + explicit missing flag.

    Categorical context:
    - camera make;
    - camera model, when reliably available.

    Camera strings are never fabricated from filenames.
    """

    def run(
        self,
        data: PreprocessedInput,
    ) -> FeatureExtractionResult:
        if data.decoded_frame is None:
            raise ValueError(
                "UnifiedFeatureExtractor דורש decoded RAW frame."
            )

        pixel_stats = compute_pixel_statistics(
            data.decoded_frame
        )
        pixel_vector = pixel_statistics_feature_vector(
            pixel_stats
        )

        metadata_result = MetadataFeatureExtractor(
            version="metadata-features-v1",
        ).run(data)
        metadata_vector = metadata_result.features

        names: list[str] = []
        values: list[float] = []

        for name, value in zip(
            pixel_vector.feature_names,
            pixel_vector.values,
        ):
            names.append(f"pixel.{name}")
            values.append(float(value))

        for name, value in zip(
            metadata_vector.feature_names,
            metadata_vector.values,
        ):
            names.append(f"exif.{name}")
            values.append(float(value))

        wb = data.source.raw_wb
        if wb is None:
            wb = data.decoded_frame.metadata.camera_wb

        red_over_green, blue_over_green = _normalized_wb(wb)

        names.extend(
            (
                "wb.red_over_green",
                "wb.red_over_green__missing",
                "wb.blue_over_green",
                "wb.blue_over_green__missing",
            )
        )

        if red_over_green is None or blue_over_green is None:
            values.extend((0.0, 1.0, 0.0, 1.0))
        else:
            values.extend(
                (
                    float(red_over_green),
                    0.0,
                    float(blue_over_green),
                    0.0,
                )
            )

        matrix = data.decoded_frame.metadata.rgb_xyz_matrix
        for index in range(12):
            names.append(f"camera.rgb_xyz_{index:02d}")
            if matrix is None:
                values.append(0.0)
            else:
                values.append(float(matrix[index]))

        names.append("camera.rgb_xyz__missing")
        values.append(1.0 if matrix is None else 0.0)

        categorical: list[tuple[str, str]] = []

        if data.source.camera.make:
            categorical.append(
                ("camera.make", data.source.camera.make)
            )

        if data.source.camera.model:
            categorical.append(
                ("camera.model", data.source.camera.model)
            )

        vector = FeatureVector(
            version=UNIFIED_FEATURE_VERSION,
            values=tuple(values),
            feature_names=tuple(names),
            categorical_context=tuple(categorical),
        )
        vector.validate()

        return FeatureExtractionResult(
            preprocessed=data,
            features=vector,
        )
