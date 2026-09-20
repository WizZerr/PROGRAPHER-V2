from __future__ import annotations

from typing import Any

from app.domain.recipes import ProcessFamily, validate_recipe


def _format_number(value: float, *, decimals: int = 0, signed: bool = False) -> str:
    if decimals <= 0:
        text = str(int(round(value)))
    else:
        text = f"{value:.{decimals}f}"

    if signed and value > 0:
        return f"+{text}"

    return text


def recipe_to_xmp_attributes(
    recipe: dict[str, Any],
    family: ProcessFamily,
) -> tuple[dict[str, float], dict[str, str]]:
    clean = validate_recipe(recipe, family)

    attrs: dict[str, str] = {}

    if "temperature" in clean or "tint" in clean:
        attrs["WhiteBalance"] = "Custom"

    if "temperature" in clean:
        attrs["Temperature"] = _format_number(clean["temperature"])

    if "tint" in clean:
        attrs["Tint"] = _format_number(clean["tint"], signed=True)

    if family == ProcessFamily.MODERN:
        mapping = {
            "exposure": ("Exposure2012", 2, True),
            "contrast": ("Contrast2012", 0, True),
            "highlights": ("Highlights2012", 0, True),
            "shadows": ("Shadows2012", 0, True),
            "whites": ("Whites2012", 0, True),
            "blacks": ("Blacks2012", 0, True),
            "clarity": ("Clarity2012", 0, True),
            "vibrance": ("Vibrance", 0, True),
            "saturation": ("Saturation", 0, True),
        }
    else:
        # In the pre-2012 Camera Raw schema, Lightroom's legacy Blacks
        # slider is serialized as crs:Shadows. It is intentionally NOT
        # treated as modern Shadows2012.
        mapping = {
            "exposure": ("Exposure", 2, True),
            "contrast": ("Contrast", 0, True),
            "blacks": ("Shadows", 0, False),
            "brightness": ("Brightness", 0, True),
            "recovery": ("HighlightRecovery", 0, False),
            "fill_light": ("FillLight", 0, False),
            "clarity": ("Clarity", 0, True),
            "vibrance": ("Vibrance", 0, True),
            "saturation": ("Saturation", 0, True),
        }

    for key, (xmp_key, decimals, signed) in mapping.items():
        if key in clean:
            attrs[xmp_key] = _format_number(
                clean[key],
                decimals=decimals,
                signed=signed,
            )

    return clean, attrs
