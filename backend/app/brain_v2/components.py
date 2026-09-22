from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.brain_v2.contracts import (
    Availability,
    BrainInput,
    CameraInfo,
    EditRecipe,
    FeatureVector,
    PreprocessingInfo,
)

if TYPE_CHECKING:
    from app.brain_v2.preprocessing.raw_decode import DecodedRawFrame


@dataclass(frozen=True)
class RawInputRecord:
    source_fingerprint: str
    event_id: str
    camera: CameraInfo
    captured_at: str | None
    raw_wb: tuple[float, ...] | None
    exif: dict[str, float | int | str | None]
    missing_fields: tuple[str, ...]
    raw_path: str | None = None


@dataclass(frozen=True)
class PreprocessedInput:
    source: RawInputRecord
    preprocessing: PreprocessingInfo
    numeric_metadata: dict[str, float]
    decoded_frame: DecodedRawFrame | None = None


@dataclass(frozen=True)
class FeatureExtractionResult:
    preprocessed: PreprocessedInput
    features: FeatureVector


@dataclass(frozen=True)
class QualityResult:
    availability: Availability
    requires_full_review: bool
    confidence: float | None = None
    reason: str | None = None

    def validate(self) -> None:
        self.availability.validate()

        if self.availability.state == "not_available":
            if self.confidence is not None:
                raise ValueError(
                    "אסור להמציא confidence כאשר Quality/Critic אינו זמין."
                )
            if not self.requires_full_review:
                raise ValueError(
                    "כאשר Critic אינו זמין יש לדרוש בדיקה מלאה."
                )


@dataclass(frozen=True)
class BrainPipelineResult:
    brain_input: BrainInput
    base_recipe: EditRecipe
    adapted_recipe: EditRecipe
    final_recipe: EditRecipe
    quality: QualityResult
    executed_components: tuple[str, ...]


class Preprocessor(Protocol):
    def run(self, raw: RawInputRecord) -> PreprocessedInput:
        ...


class FeatureExtractor(Protocol):
    def run(self, data: PreprocessedInput) -> FeatureExtractionResult:
        ...


class BaseModel(Protocol):
    def predict(self, brain_input: BrainInput) -> EditRecipe:
        ...


class PhotographerAdapter(Protocol):
    def apply(
        self,
        brain_input: BrainInput,
        recipe: EditRecipe,
    ) -> EditRecipe:
        ...


class EventContext(Protocol):
    def apply(
        self,
        brain_input: BrainInput,
        recipe: EditRecipe,
    ) -> EditRecipe:
        ...


class QualityControl(Protocol):
    def evaluate(
        self,
        brain_input: BrainInput,
        recipe: EditRecipe,
    ) -> QualityResult:
        ...
