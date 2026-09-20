from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

RECIPE_KEYS = [
    "exposure",
    "highlights",
    "shadows",
    "whites",
    "blacks",
    "contrast",
    "temperature",
    "vibrance",
    "clarity",
]

STYLE_ACCEPTED = {
    "approved",
    "selected_default",
    "selected_final",
    "מושלם",
}

def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows

def parse_json_field(value):
    if value in (None, "", {}):
        return None
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except Exception:
        return None

def get_nested(metadata: dict, *keys, default=None):
    if metadata is None:
        return default
    lowered = {str(k).lower(): v for k, v in metadata.items()}
    for key in keys:
        key_l = str(key).lower()
        if key_l in lowered:
            return lowered[key_l]
    return default

def to_float(value, default=0.0):
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", "")
            if value.startswith("1/"):
                denom = float(value.split("/", 1)[1])
                return 1.0 / denom if denom else default
        return float(value)
    except Exception:
        return default

def extract_numeric_metadata(metadata: dict) -> dict[str, float]:
    return {
        "iso": to_float(get_nested(metadata, "iso", "isospeedratings"), 0.0),
        "aperture": to_float(get_nested(metadata, "fnumber", "aperture", "aperturevalue"), 0.0),
        "focal_length": to_float(get_nested(metadata, "focallength", "focal_length"), 0.0),
        "shutter_seconds": to_float(get_nested(metadata, "exposuretime", "shutterspeed", "shutter_speed"), 0.0),
        "width": to_float(get_nested(metadata, "width", "imagewidth"), 0.0),
        "height": to_float(get_nested(metadata, "height", "imageheight"), 0.0),
    }

def build_semantic_feature_names(record: dict) -> tuple[list[str], list[float]]:
    semantics = (record.get("semantics") or {})
    groups = semantics.get("groups") or {}
    feature_names: list[str] = []
    feature_values: list[float] = []

    for group_name in ["scene", "lighting", "people", "framing", "technical"]:
        candidates = groups.get(group_name) or []
        # top-1 label one-hot-ish key presence with score and top-2 margin
        if candidates:
            top = candidates[0]
            feature_names.append(f"{group_name}__top_score")
            feature_values.append(float(top.get("score_percent", 0.0)) / 100.0)
            feature_names.append(f"{group_name}__top_key_hash")
            stable = hashlib.sha256(str(top.get("key") or "").encode("utf-8")).digest()
            feature_values.append(int.from_bytes(stable[:4], "big") / 4294967295.0)
            if len(candidates) > 1:
                margin = float(top.get("score_percent", 0.0)) - float(candidates[1].get("score_percent", 0.0))
            else:
                margin = float(top.get("score_percent", 0.0))
            feature_names.append(f"{group_name}__margin")
            feature_values.append(margin / 100.0)
        else:
            feature_names.extend([
                f"{group_name}__top_score",
                f"{group_name}__top_key_hash",
                f"{group_name}__margin",
            ])
            feature_values.extend([0.0, 0.0, 0.0])

    return feature_names, feature_values

def record_target_recipe(record: dict):
    feedback = record.get("feedback") or {}
    verdict = str(feedback.get("verdict") or "")
    analysis = record.get("analysis") or {}

    if verdict == "corrected":
        photographer_recipe = parse_json_field(feedback.get("photographer_recipe_json"))
        if photographer_recipe:
            return {k: float(photographer_recipe.get(k, 0.0)) for k in RECIPE_KEYS}

    if verdict in STYLE_ACCEPTED:
        recipe = analysis.get("recipe") or {}
        if recipe:
            return {k: float(recipe.get(k, 0.0)) for k in RECIPE_KEYS}

    return None

def build_feature_vector(record: dict):
    embedding = record.get("embedding") or []
    if not embedding:
        return None, None

    embedding = [float(x) for x in embedding]
    metadata = extract_numeric_metadata(record.get("metadata") or {})
    semantic_names, semantic_values = build_semantic_feature_names(record)

    meta_names = list(metadata.keys())
    meta_values = [float(metadata[name]) for name in meta_names]

    feature_names = [f"embed_{i}" for i in range(len(embedding))] + meta_names + semantic_names
    feature_values = embedding + meta_values + semantic_values
    return feature_names, feature_values
