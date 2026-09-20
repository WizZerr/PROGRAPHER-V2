from __future__ import annotations

import math
from enum import StrEnum
from typing import Any


class ProcessFamily(StrEnum):
    MODERN = "modern"
    LEGACY = "legacy"


class RecipeValidationError(ValueError):
    pass


COMMON_SPECS: dict[str, tuple[float, float, int]] = {
    "exposure": (-5.0, 5.0, 2),
    "temperature": (2000.0, 50000.0, 0),
    "tint": (-150.0, 150.0, 1),
    "clarity": (-100.0, 100.0, 1),
    "vibrance": (-100.0, 100.0, 1),
    "saturation": (-100.0, 100.0, 1),
}

MODERN_SPECS: dict[str, tuple[float, float, int]] = {
    **COMMON_SPECS,
    "contrast": (-100.0, 100.0, 1),
    "highlights": (-100.0, 100.0, 1),
    "shadows": (-100.0, 100.0, 1),
    "whites": (-100.0, 100.0, 1),
    "blacks": (-100.0, 100.0, 1),
}

LEGACY_SPECS: dict[str, tuple[float, float, int]] = {
    **COMMON_SPECS,
    "contrast": (-100.0, 100.0, 1),
    "blacks": (0.0, 100.0, 1),
    "brightness": (-150.0, 150.0, 1),
    "recovery": (0.0, 100.0, 1),
    "fill_light": (0.0, 100.0, 1),
}


def specs_for_family(family: ProcessFamily) -> dict[str, tuple[float, float, int]]:
    return MODERN_SPECS if family == ProcessFamily.MODERN else LEGACY_SPECS


def _number(key: str, value: Any) -> float:
    if value is None or isinstance(value, bool):
        raise RecipeValidationError(f"{key}: expected a finite number")

    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RecipeValidationError(f"{key}: expected a finite number") from exc

    if not math.isfinite(number):
        raise RecipeValidationError(f"{key}: expected a finite number")

    return number


def validate_recipe(
    recipe: dict[str, Any],
    family: ProcessFamily,
) -> dict[str, float]:
    """
    Validate without silent clipping.

    Missing fields stay missing. Values outside the supported Lightroom
    contract raise an explicit error instead of being silently clamped.
    """
    specs = specs_for_family(family)
    clean: dict[str, float] = {}

    for key, raw_value in recipe.items():
        if key not in specs:
            raise RecipeValidationError(
                f"{key}: parameter is not supported for process family '{family.value}'"
            )

        minimum, maximum, precision = specs[key]
        number = _number(key, raw_value)

        if number < minimum or number > maximum:
            raise RecipeValidationError(
                f"{key}: {number} is outside supported range "
                f"[{minimum}, {maximum}] for '{family.value}'"
            )

        clean[key] = round(number, precision)

    return clean
