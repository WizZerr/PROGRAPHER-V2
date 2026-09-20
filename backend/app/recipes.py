from __future__ import annotations

import math
from typing import Any, Optional


RECIPE_CONTRACT_VERSION = "prographer-edit-recipe-v1"

# One canonical language for every future ProGrapher edit, regardless of
# whether the value came from Lightroom Legacy, PV2012+, V1, V2, XMP, or the
# Darkroom UI.  Temperature is ALWAYS absolute Kelvin in this contract.
RECIPE_PARAMETER_SPECS: dict[str, dict[str, Any]] = {
    "exposure": {
        "label_he": "חשיפה",
        "unit": "stops",
        "min": -5.0,
        "max": 5.0,
        "precision": 2,
        "family": "tone",
    },
    "contrast": {
        "label_he": "ניגודיות",
        "unit": "slider",
        "min": -100.0,
        "max": 100.0,
        "precision": 1,
        "family": "tone",
    },
    "highlights": {
        "label_he": "אזורים בהירים",
        "unit": "slider",
        "min": -100.0,
        "max": 100.0,
        "precision": 1,
        "family": "tone",
    },
    "shadows": {
        "label_he": "צללים",
        "unit": "slider",
        "min": -100.0,
        "max": 100.0,
        "precision": 1,
        "family": "tone",
    },
    "whites": {
        "label_he": "לבנים",
        "unit": "slider",
        "min": -100.0,
        "max": 100.0,
        "precision": 1,
        "family": "tone",
    },
    "blacks": {
        "label_he": "שחורים",
        "unit": "legacy_slider",
        "min": 0.0,
        "max": 100.0,
        "precision": 1,
        "family": "legacy_tone",
    },
    "temperature": {
        "label_he": "טמפרטורה",
        "unit": "kelvin",
        "min": 2000.0,
        "max": 50000.0,
        "precision": 0,
        "family": "white_balance",
    },
    "tint": {
        "label_he": "גוון",
        "unit": "slider",
        "min": -150.0,
        "max": 150.0,
        "precision": 1,
        "family": "white_balance",
    },
    "clarity": {
        "label_he": "בהירות מקומית",
        "unit": "slider",
        "min": -100.0,
        "max": 100.0,
        "precision": 1,
        "family": "presence",
    },
    "vibrance": {
        "label_he": "חיוניות",
        "unit": "slider",
        "min": -100.0,
        "max": 100.0,
        "precision": 1,
        "family": "presence",
    },
    "saturation": {
        "label_he": "רוויה",
        "unit": "slider",
        "min": -100.0,
        "max": 100.0,
        "precision": 1,
        "family": "presence",
    },
    "brightness": {
        "label_he": "בהירות Legacy",
        "unit": "legacy_slider",
        "min": -150.0,
        "max": 150.0,
        "precision": 1,
        "family": "legacy_tone",
    },
    "recovery": {
        "label_he": "שחזור Legacy",
        "unit": "legacy_slider",
        "min": 0.0,
        "max": 100.0,
        "precision": 1,
        "family": "legacy_tone",
    },
    "fill_light": {
        "label_he": "Fill Light Legacy",
        "unit": "legacy_slider",
        "min": 0.0,
        "max": 100.0,
        "precision": 1,
        "family": "legacy_tone",
    },
}


def recipe_contract_public() -> dict[str, Any]:
    return {
        "version": RECIPE_CONTRACT_VERSION,
        "temperature_semantics": "absolute_kelvin",
        "missing_value_semantics": "parameter_not_applied_or_not_supported",
        "parameters": RECIPE_PARAMETER_SPECS,
    }


def _number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def clamp_recipe_value(key: str, value: Any) -> Optional[float]:
    spec = RECIPE_PARAMETER_SPECS.get(key)
    if spec is None:
        return None
    number = _number(value)
    if number is None:
        return None
    number = max(float(spec["min"]), min(float(spec["max"]), number))
    precision = int(spec.get("precision", 1))
    return round(number, precision)


def canonicalize_recipe(recipe: dict[str, Any], *, include_unknown: bool = False) -> dict[str, float]:
    """Convert any recipe-like mapping into the Production EditRecipe V1 contract."""
    clean: dict[str, float] = {}
    for key in RECIPE_PARAMETER_SPECS:
        if key not in recipe:
            continue
        value = clamp_recipe_value(key, recipe.get(key))
        if value is not None:
            clean[key] = value

    if include_unknown:
        for key, value in recipe.items():
            if key in clean or key in RECIPE_PARAMETER_SPECS:
                continue
            number = _number(value)
            if number is not None:
                clean[str(key)] = number
    return clean


def contract_value_is_kelvin(key: str) -> bool:
    return key == "temperature"
