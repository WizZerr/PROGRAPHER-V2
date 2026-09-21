from __future__ import annotations

from app.brain_v2.components import (
    FeatureExtractionResult,
    PreprocessedInput,
)
from app.brain_v2.contracts import FeatureVector


FEATURE_ORDER = (
    "iso",
    "shutter_seconds",
    "aperture",
    "focal_length_mm",
)


class MetadataFeatureExtractor:
    """
    Deterministic technical feature extractor used only to validate the Brain
    V2 boundaries. Missing numeric metadata is represented by two values:
    value=0 and a separate missing flag. This is a feature encoding choice,
    not a claim that the source metadata itself was zero.
    """

    def __init__(
        self,
        *,
        version: str = "metadata-features-v1",
    ) -> None:
        self.version = version

    def run(
        self,
        data: PreprocessedInput,
    ) -> FeatureExtractionResult:
        values: list[float] = []
        names: list[str] = []

        for name in FEATURE_ORDER:
            present = name in data.numeric_metadata
            values.append(data.numeric_metadata.get(name, 0.0))
            names.append(name)
            values.append(0.0 if present else 1.0)
            names.append(f"{name}__missing")

        features = FeatureVector(
            version=self.version,
            values=tuple(values),
            feature_names=tuple(names),
        )
        features.validate()

        return FeatureExtractionResult(
            preprocessed=data,
            features=features,
        )
