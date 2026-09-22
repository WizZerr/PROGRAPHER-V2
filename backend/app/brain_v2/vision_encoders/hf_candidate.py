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
    """
    Runtime adapter for the controlled Phase 11 encoder experiment.

    CLIP uses the vision-only model with projection.
    DINOv3 uses AutoModel and the checkpoint's own image processor.

    Model downloads happen only when load() is explicitly called.
    """

    encoder_id: str
    device: str = "cpu"

    def __post_init__(self) -> None:
        descriptor = get_encoder_descriptor(self.encoder_id)
        if descriptor.family == "measured":
            raise ValueError(
                "HuggingFaceVisionEncoder אינו מיועד ל-measured candidate."
            )
        if self.device not in {"cpu", "cuda", "mps"}:
            raise ValueError("device לא נתמך.")
        self.descriptor = descriptor
        self._processor: Any = None
        self._model: Any = None

    def load(self) -> None:
        try:
            if self.descriptor.family == "clip":
                from transformers import (
                    CLIPImageProcessor,
                    CLIPVisionModelWithProjection,
                )

                self._processor = CLIPImageProcessor.from_pretrained(
                    self.descriptor.model_id
                )
                self._model = CLIPVisionModelWithProjection.from_pretrained(
                    self.descriptor.model_id
                )
            elif self.descriptor.family == "dinov3":
                from transformers import AutoImageProcessor, AutoModel

                self._processor = AutoImageProcessor.from_pretrained(
                    self.descriptor.model_id
                )
                self._model = AutoModel.from_pretrained(
                    self.descriptor.model_id
                )
            else:
                raise RuntimeError(
                    f"Unsupported encoder family: {self.descriptor.family}"
                )
        except ImportError as exc:
            raise RuntimeError(
                "torch/transformers אינם מותקנים במסלול הניסוי."
            ) from exc

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

        pooled = getattr(outputs, "image_embeds", None)
        if pooled is None:
            pooled = getattr(outputs, "pooler_output", None)

        if pooled is None:
            last_hidden = getattr(outputs, "last_hidden_state", None)
            if last_hidden is None:
                raise RuntimeError(
                    "המודל לא החזיר embedding מוכר."
                )
            # Fallback only for models without an official pooled output.
            pooled = last_hidden[:, 0, :]

        vector_np = (
            pooled[0]
            .detach()
            .to("cpu")
            .float()
            .numpy()
            .astype(np.float32, copy=False)
            .reshape(-1)
        )

        vector = tuple(float(value) for value in vector_np)

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

    def unload(self) -> None:
        self._model = None
        self._processor = None

        try:
            import torch

            if self.device == "cuda" and torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
