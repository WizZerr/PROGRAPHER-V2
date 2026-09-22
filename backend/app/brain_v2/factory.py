from __future__ import annotations

from app.brain_v2.adapters import NoOpPhotographerAdapter
from app.brain_v2.event_context import NoOpEventContext
from app.brain_v2.features import (
    MetadataFeatureExtractor,
    UnifiedFeatureExtractor,
)
from app.brain_v2.inference import BrainV2Pipeline
from app.brain_v2.models import FixedBaselineModel
from app.brain_v2.preprocessing import (
    MetadataPreprocessor,
    RawPixelPreprocessor,
)
from app.brain_v2.preprocessing.raw_decode import RawDecoderBackend
from app.brain_v2.quality import NoOpQualityControl


def create_experimental_pipeline() -> BrainV2Pipeline:
    """
    Phase 10 wiring-only path.
    """
    return BrainV2Pipeline(
        preprocessor=MetadataPreprocessor(),
        feature_extractor=MetadataFeatureExtractor(),
        base_model=FixedBaselineModel(),
        photographer_adapter=NoOpPhotographerAdapter(),
        event_context=NoOpEventContext(),
        quality_control=NoOpQualityControl(),
    )


def create_phase11_raw_pipeline(
    *,
    raw_backend: RawDecoderBackend | None = None,
) -> BrainV2Pipeline:
    """
    Real RAW -> unified features path.

    The base model is still wiring-only; Phase 11 validates the input,
    not editing quality.
    """
    return BrainV2Pipeline(
        preprocessor=RawPixelPreprocessor(
            backend=raw_backend,
        ),
        feature_extractor=UnifiedFeatureExtractor(),
        base_model=FixedBaselineModel(),
        photographer_adapter=NoOpPhotographerAdapter(),
        event_context=NoOpEventContext(),
        quality_control=NoOpQualityControl(),
    )
