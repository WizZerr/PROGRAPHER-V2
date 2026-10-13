"""SP-01.03: local, zero-shot, full-ranking diagnostics on neutral JPEG only.

This adapter deliberately does not modify the existing RAW scene-analysis path.
Scores are relative across eight fixed prompts, NOT calibrated probabilities.
The human label is added AFTER inference; never part of the visual model input.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Sequence

from PIL import Image

from app.photographer.raw_auto_scene_review import (
    MODEL_ID, PROMPTS, PROMPT_KEYS, _rank_relative,
)

PROMPT_SET_VERSION = "sp01-existing-wedding-scenes-v1"
PROMPT_SHA256 = hashlib.sha256(
    json.dumps(
        {"keys": PROMPT_KEYS, "prompts": PROMPTS},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()


def ranked_scene_report(scores: Sequence[float]) -> dict[str, Any]:
    """Produce all eight relative scores plus the unchanged abstention policy."""
    numeric = [float(value) for value in scores]
    if len(numeric) != len(PROMPT_KEYS) or any(not math.isfinite(v) for v in numeric):
        raise ValueError("invalid scene scores")
    guess = _rank_relative(numeric)
    indices = sorted(range(len(numeric)), key=lambda i: (-numeric[i], i))
    full_ranking = [
        {"rank": rank, "label": PROMPT_KEYS[index],
         "relative_score": round(numeric[index], 6)}
        for rank, index in enumerate(indices, start=1)
    ]
    return {
        **guess,
        "ranking": full_ranking,
        "top_3": full_ranking[:3],
        "model_id": MODEL_ID,
        "prompt_set_version": PROMPT_SET_VERSION,
        "prompt_sha256": PROMPT_SHA256,
        "scores_are_calibrated_probabilities": False,
    }


def after_inference_human_review(
    report: dict[str, Any], label: str,
) -> dict[str, Any]:
    """Attach one human-confirmed label AFTER model output is finalized.

    Returns private evaluation data. Does not change suggestion/ranking.
    """
    if label not in PROMPT_KEYS:
        raise ValueError("human label is not a supported concrete scene")
    ranking = report.get("ranking")
    if not isinstance(ranking, list) or len(ranking) != len(PROMPT_KEYS):
        raise ValueError("review requires the complete relative ranking")
    matches = [item for item in ranking if item.get("label") == label]
    if len(matches) != 1:
        raise ValueError("human label absent/duplicated in ranking")
    top = report.get("raw_top_label")
    suggestion = report.get("suggested_label")
    return {
        "human_confirmed_scene": label,
        "human_label_is_model_input": False,
        "ground_truth_rank": matches[0]["rank"],
        "ground_truth_relative_score": matches[0]["relative_score"],
        "top_1_matches_ground_truth": top == label,
        "final_suggestion_matches_ground_truth": suggestion == label,
        "safe_abstention_on_wrong_top_1": (
            top != label and suggestion == "UNKNOWN" and report.get("abstained") is True
        ),
        "evaluation_status": "SINGLE_HUMAN_LABELED_RESEARCH_EXAMPLE_NOT_ACCURACY",
    }


class RankedSmartPreviewClip:
    """Separate SP-01 runtime: same CLIP model as RAW, explicit slow processor."""

    def __init__(self, *, allow_model_download: bool = False):
        try:
            import torch
            import transformers
            from transformers import AutoProcessor, AutoModelForZeroShotImageClassification
        except ImportError as exc:
            raise RuntimeError("Local vision runtime is not installed") from exc
        try:
            # Pin slow preprocessing behavior in SP-01. The library's future
            # default may change; this research route must not drift silently.
            self.processor = AutoProcessor.from_pretrained(
                MODEL_ID, local_files_only=not allow_model_download, use_fast=False
            )
            self.model = AutoModelForZeroShotImageClassification.from_pretrained(
                MODEL_ID, local_files_only=not allow_model_download, use_safetensors=True
            )
        except (OSError, ValueError) as exc:
            raise RuntimeError(
                "Local CLIP weights unavailable; no photo upload or implicit download"
            ) from exc
        self.model.eval()
        self.torch = torch
        self.runtime = {
            "transformers_version": transformers.__version__,
            "torch_version": torch.__version__,
            "processor_use_fast": False,
            "model_identifier_is_not_pinned_revision": True,
        }

    def predict(self, neutral_srgb_jpeg: Image.Image) -> dict[str, Any]:
        inputs = self.processor(
            text=PROMPTS,
            images=neutral_srgb_jpeg.convert("RGB"),
            return_tensors="pt",
            padding=True,
        )
        with self.torch.inference_mode():
            logits = self.model(**inputs).logits_per_image[0]
            scores = self.torch.softmax(logits, dim=-1).detach().cpu().tolist()
        return {**ranked_scene_report(scores), "runtime": self.runtime}
