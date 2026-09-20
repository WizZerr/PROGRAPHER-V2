from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .prompts import PROMPT_GROUPS


class BrainUnavailableError(RuntimeError):
    pass


_LOCK = threading.Lock()
_BRAIN: "LocalVisionBrain | None" = None


def _dependency_probe() -> dict[str, Any]:
    result: dict[str, Any] = {
        "torch_installed": False,
        "transformers_installed": False,
        "cuda_available": False,
        "cuda_device": None,
        "torch_version": None,
        "transformers_version": None,
    }

    try:
        import torch  # type: ignore
        result["torch_installed"] = True
        result["torch_version"] = getattr(torch, "__version__", None)
        result["cuda_available"] = bool(torch.cuda.is_available())
        if result["cuda_available"]:
            result["cuda_device"] = torch.cuda.get_device_name(0)
    except Exception:
        pass

    try:
        import transformers  # type: ignore
        result["transformers_installed"] = True
        result["transformers_version"] = getattr(transformers, "__version__", None)
    except Exception:
        pass

    return result


def brain_status() -> dict[str, Any]:
    deps = _dependency_probe()
    model_name = os.getenv(
        "PROGRAPHER_VISION_MODEL",
        "openai/clip-vit-base-patch32",
    ).strip()

    loaded = _BRAIN is not None and _BRAIN.loaded
    device = _BRAIN.device if loaded else (
        "cuda" if deps["cuda_available"] else "cpu"
    )

    return {
        "ok": True,
        "engine": "Local Vision Brain V1",
        "model_name": model_name,
        "loaded": loaded,
        "device": device,
        **deps,
    }


class LocalVisionBrain:
    def __init__(self) -> None:
        self.model_name = os.getenv(
            "PROGRAPHER_VISION_MODEL",
            "openai/clip-vit-base-patch32",
        ).strip()
        self.requested_device = os.getenv(
            "PROGRAPHER_AI_DEVICE",
            "auto",
        ).strip().lower()
        self.loaded = False
        self.device = "cpu"
        self.model = None
        self.processor = None
        self.torch = None
        self._text_cache: dict[str, Any] = {}

    def warmup(self) -> dict[str, Any]:
        self._ensure_loaded()
        return {
            "ok": True,
            "model_name": self.model_name,
            "device": self.device,
            "loaded": True,
            "embedding_dimensions": int(self.model.config.projection_dim),
            "groups": list(PROMPT_GROUPS.keys()),
        }

    def _ensure_loaded(self) -> None:
        if self.loaded:
            return

        try:
            import torch  # type: ignore
            from transformers import CLIPModel, CLIPProcessor  # type: ignore
        except Exception as exc:
            raise BrainUnavailableError(
                "רכיבי ה-AI המקומי אינם מותקנים. הפעל install_ai_brain.bat ואז נסה שוב."
            ) from exc

        if self.requested_device == "cpu":
            device = "cpu"
        elif self.requested_device == "cuda":
            if not torch.cuda.is_available():
                raise BrainUnavailableError(
                    "CUDA הוגדר ידנית אבל PyTorch לא מזהה כרטיס מסך CUDA."
                )
            device = "cuda"
        else:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        try:
            processor = CLIPProcessor.from_pretrained(self.model_name)
            model = CLIPModel.from_pretrained(self.model_name)
        except Exception as exc:
            raise BrainUnavailableError(
                "לא ניתן לטעון את מודל ה-Vision. בהרצה הראשונה נדרש חיבור אינטרנט כדי להוריד אותו למחשב."
            ) from exc

        model.eval()
        model.to(device)

        self.torch = torch
        self.processor = processor
        self.model = model
        self.device = device
        self.loaded = True

    def _text_features(self, group_name: str):
        if group_name in self._text_cache:
            return self._text_cache[group_name]

        group = PROMPT_GROUPS[group_name]
        prompts = [item[2] for item in group]
        inputs = self.processor(
            text=prompts,
            return_tensors="pt",
            padding=True,
            truncation=True,
        )
        inputs = {
            key: value.to(self.device)
            for key, value in inputs.items()
        }

        with self.torch.inference_mode():
            features = self.model.get_text_features(**inputs)
            features = features / features.norm(dim=-1, keepdim=True)

        self._text_cache[group_name] = features
        return features

    def _score_group(
        self,
        image_features,
        group_name: str,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        group = PROMPT_GROUPS[group_name]
        text_features = self._text_features(group_name)

        similarities = image_features @ text_features.T
        probabilities = self.torch.softmax(
            similarities * 20.0,
            dim=-1,
        )[0]

        k = min(top_k, len(group))
        values, indices = probabilities.topk(k)

        output = []
        for value, index in zip(values.tolist(), indices.tolist()):
            key, label_he, _prompt = group[index]
            output.append({
                "key": key,
                "label_he": label_he,
                "score_percent": round(float(value) * 100.0, 2),
            })

        return output

    def _result_from_features(self, image_features, index: int = 0) -> dict[str, Any]:
        single = image_features[index:index + 1]
        embedding = [
            round(float(x), 7)
            for x in single[0].detach().cpu().tolist()
        ]
        groups = {
            group_name: self._score_group(single, group_name)
            for group_name in PROMPT_GROUPS
        }
        top_summary = {
            group_name: candidates[0] if candidates else None
            for group_name, candidates in groups.items()
        }
        return {
            "model_name": self.model_name,
            "device": self.device,
            "embedding_dimensions": len(embedding),
            "embedding": embedding,
            "groups": groups,
            "top": top_summary,
            "source": "preview",
        }

    def analyze_image(self, image: Image.Image) -> dict[str, Any]:
        self._ensure_loaded()
        image = ImageOps.exif_transpose(image).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        pixel_values = inputs["pixel_values"].to(self.device)
        with self.torch.inference_mode():
            features = self.model.get_image_features(pixel_values=pixel_values)
            features = features / features.norm(dim=-1, keepdim=True)
        return self._result_from_features(features, 0)

    def analyze_images(self, images: list[Image.Image]) -> list[dict[str, Any]]:
        self._ensure_loaded()
        if not images:
            return []
        prepared = [ImageOps.exif_transpose(img).convert("RGB") for img in images]
        inputs = self.processor(images=prepared, return_tensors="pt")
        pixel_values = inputs["pixel_values"].to(self.device)
        with self.torch.inference_mode():
            features = self.model.get_image_features(pixel_values=pixel_values)
            features = features / features.norm(dim=-1, keepdim=True)
        return [self._result_from_features(features, i) for i in range(len(prepared))]

    def analyze(self, image_path: Path) -> dict[str, Any]:
        self._ensure_loaded()
        with Image.open(image_path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        return self.analyze_image(image)


def get_brain() -> LocalVisionBrain:
    global _BRAIN
    if _BRAIN is None:
        with _LOCK:
            if _BRAIN is None:
                _BRAIN = LocalVisionBrain()
    return _BRAIN
