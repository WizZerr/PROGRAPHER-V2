from __future__ import annotations

from app.brain_v2.adapters import NoOpPhotographerAdapter
from app.brain_v2.features import MetadataFeatureExtractor
from app.brain_v2.inference import BrainV2Pipeline
from app.brain_v2.models import FixedBaselineModel
from app.brain_v2.preprocessing import MetadataPreprocessor
from app.brain_v2.event_context import NoOpEventContext
from app.brain_v2.quality import NoOpQualityControl


def create_experimental_pipeline() -> BrainV2Pipeline:
    """
    Phase 10 wiring only.

    No component here is presented as a production-quality editing brain.
    """
    return BrainV2Pipeline(
        preprocessor=MetadataPreprocessor(),
        feature_extractor=MetadataFeatureExtractor(),
        base_model=FixedBaselineModel(),
        photographer_adapter=NoOpPhotographerAdapter(),
        event_context=NoOpEventContext(),
        quality_control=NoOpQualityControl(),
    )
