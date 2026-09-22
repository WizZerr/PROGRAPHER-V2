from __future__ import annotations

from app.brain_v2.contracts import BrainInput
from app.brain_v2.vision_encoders.contracts import EncoderResult
from app.brain_v2.vision_encoders.registry import SIMPLE_MEASURED_ID


class SimpleMeasuredEncoder:
    encoder_id = SIMPLE_MEASURED_ID
    encoder_version = "1"

    def encode(self, brain_input: BrainInput) -> EncoderResult:
        brain_input.validate()
        vector = tuple(float(value) for value in brain_input.features.values)

        if not vector:
            raise ValueError(
                "SimpleMeasuredEncoder קיבל FeatureVector ריק."
            )

        result = EncoderResult(
            encoder_id=self.encoder_id,
            encoder_version=self.encoder_version,
            vector=vector,
            dimension=len(vector),
            device="cpu",
            input_contract=brain_input.features.version,
        )
        result.validate()
        return result
