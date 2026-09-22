from __future__ import annotations

from app.brain_v2.components import (
    BaseModel,
    BrainPipelineResult,
    EventContext,
    FeatureExtractor,
    PhotographerAdapter,
    Preprocessor,
    QualityControl,
    RawInputRecord,
)
from app.brain_v2.contracts import Availability, BrainInput


class BrainV2Pipeline:
    def __init__(
        self,
        *,
        preprocessor: Preprocessor,
        feature_extractor: FeatureExtractor,
        base_model: BaseModel,
        photographer_adapter: PhotographerAdapter,
        event_context: EventContext,
        quality_control: QualityControl,
    ) -> None:
        self.preprocessor = preprocessor
        self.feature_extractor = feature_extractor
        self.base_model = base_model
        self.photographer_adapter = photographer_adapter
        self.event_context = event_context
        self.quality_control = quality_control

    def run(self, raw: RawInputRecord) -> BrainPipelineResult:
        executed: list[str] = []

        preprocessed = self.preprocessor.run(raw)
        executed.append("preprocessing")

        extracted = self.feature_extractor.run(preprocessed)
        executed.append("features")

        # Important: preprocessing may recover trustworthy metadata directly
        # from the RAW decoder. BrainInput must use the effective source,
        # not the incomplete pre-decode source record.
        source = preprocessed.source

        brain_input = BrainInput(
            source_fingerprint=source.source_fingerprint,
            event_id=source.event_id,
            camera=source.camera,
            captured_at=source.captured_at,
            raw_wb=source.raw_wb,
            exif=source.exif,
            missing_fields=source.missing_fields,
            preprocessing=preprocessed.preprocessing,
            features=extracted.features,
            scene_context=Availability(
                state="not_available",
                reason="Scene Context not implemented in first Brain V2 path.",
            ),
            critic=Availability(
                state="not_available",
                reason="Critic not implemented in first Brain V2 path.",
            ),
        )
        brain_input.validate()

        base_recipe = self.base_model.predict(brain_input)
        executed.append("base_model")

        adapted_recipe = self.photographer_adapter.apply(
            brain_input,
            base_recipe,
        )
        executed.append("photographer_adapter")

        final_recipe = self.event_context.apply(
            brain_input,
            adapted_recipe,
        )
        executed.append("event_context")

        quality = self.quality_control.evaluate(
            brain_input,
            final_recipe,
        )
        executed.append("quality_control")

        return BrainPipelineResult(
            brain_input=brain_input,
            base_recipe=base_recipe,
            adapted_recipe=adapted_recipe,
            final_recipe=final_recipe,
            quality=quality,
            executed_components=tuple(executed),
        )
