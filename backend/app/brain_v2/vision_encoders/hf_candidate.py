from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.brain_v2.preprocessing.raw_decode import DecodedRawFrame
from app.brain_v2.vision_encoders.contracts import EncoderResult
from app.brain_v2.vision_encoders.image_input import (
    VISION_IMAGE_INPUT_VERSION,
    frame_to_srgb_uint8,
)
from app.brain_v2.vision_encoders.registry import get_encoder_descriptor


@dataclass
class HuggingFaceVisionEncoder:
    encoder_id: str
    device: str = "cpu"

    def __post_init__(self) -> None:
        descriptor = get_encoder_descriptor(self.encoder_id)
        if descriptor.family == "measured":
            raise ValueError(
                "HuggingFaceVisionEncoder אינו מיועד ל-measured candidate."
            )
        self.descriptor = descriptor
        self._processor: Any = None
        self._model: Any = None

    def load(self) -> None:
        try:
            from transformers import AutoImageProcessor, AutoModel
        except ImportError as exc:
            raise RuntimeError(
                "transformers אינו מותקן במסלול הניסוי."
            ) from exc

        self._processor = AutoImageProcessor.from_pretrained(
            self.descriptor.model_id
        )
        self._model = AutoModel.from_pretrained(
            self.descriptor.model_id
        )
        self._model.to(self.device)
        self._model.eval()

    def encode(self, frame: DecodedRawFrame) -> EncoderResult:
        if self._processor is None or self._model is None:
            raise RuntimeError("יש לקרוא load() לפני encode().")

        import torch
        from PIL import Image

        image = Image.fromarray(
            frame_to_srgb_uint8(frame),
            mode="RGB",
        )

        inputs = self._processor(
            images=image,
            return_tensors="pt",
        )
        inputs = {
            key: value.to(self.device)
            for key, value in inputs.items()
        }

        with torch.inference_mode():
            outputs = self._model(**inputs)

        pooled = getattr(outputs, "pooler_output", None)
        if pooled is None:
            pooled = getattr(outputs, "image_embeds", None)

        if pooled is None:
            last_hidden = getattr(outputs, "last_hidden_state", None)
            if last_hidden is None:
                raise RuntimeError(
                    "המודל לא החזיר embedding מוכר."
                )
            pooled = last_hidden.mean(dim=1)

        vector_np = (
            pooled[0]
            .detach()
            .to("cpu")
            .float()
            .numpy()
            .astype(np.float32, copy=False)
        )

        vector = tuple(float(value) for value in vector_np.reshape(-1))

        result = EncoderResult(
            encoder_id=self.descriptor.encoder_id,
            encoder_version=self.descriptor.version,
            vector=vector,
            dimension=len(vector),
            device=self.device,
            input_contract=VISION_IMAGE_INPUT_VERSION,
        )
        result.validate()
        return result
