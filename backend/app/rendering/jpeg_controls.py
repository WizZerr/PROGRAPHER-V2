from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np

from app.rendering.jpeg_renderer import build_polynomial_recipe


JPEG_CONTROL_CONTRACT_VERSION = "jpeg-global-controls-v1"


class JpegControlValidationError(ValueError):
    pass


@dataclass(frozen=True)
class JpegGlobalControls:
    brightness: float = 0.0
    contrast: float = 0.0
    warmth: float = 0.0
    tint: float = 0.0


JPEG_CONTROL_SPECS: dict[str, dict[str, Any]] = {
    "brightness": {
        "minimum": -100.0,
        "maximum": 100.0,
        "step": 1.0,
        "neutral": 0.0,
        "unit": "normalized",
        "label_he": "בהירות",
    },
    "contrast": {
        "minimum": -100.0,
        "maximum": 100.0,
        "step": 1.0,
        "neutral": 0.0,
        "unit": "normalized",
        "label_he": "ניגודיות",
    },
    "warmth": {
        "minimum": -100.0,
        "maximum": 100.0,
        "step": 1.0,
        "neutral": 0.0,
        "unit": "normalized",
        "label_he": "חום צבע",
    },
    "tint": {
        "minimum": -100.0,
        "maximum": 100.0,
        "step": 1.0,
        "neutral": 0.0,
        "unit": "normalized",
        "label_he": "ירוק ↔ מג׳נטה",
    },
}


def _validate_value(name: str, raw: Any) -> float:
    if raw is None or isinstance(raw, bool):
        raise JpegControlValidationError(
            f"{name}: expected a finite numeric control value"
        )
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise JpegControlValidationError(
            f"{name}: expected a finite numeric control value"
        ) from exc
    if not math.isfinite(value):
        raise JpegControlValidationError(
            f"{name}: expected a finite numeric control value"
        )

    spec = JPEG_CONTROL_SPECS[name]
    minimum = float(spec["minimum"])
    maximum = float(spec["maximum"])
    if value < minimum or value > maximum:
        raise JpegControlValidationError(
            f"{name}: {value} is outside supported range "
            f"[{minimum}, {maximum}]"
        )
    return round(value, 4)


def validate_jpeg_controls(
    controls: JpegGlobalControls | dict[str, Any],
) -> JpegGlobalControls:
    if isinstance(controls, JpegGlobalControls):
        raw = {
            "brightness": controls.brightness,
            "contrast": controls.contrast,
            "warmth": controls.warmth,
            "tint": controls.tint,
        }
    elif isinstance(controls, dict):
        unknown = set(controls) - set(JPEG_CONTROL_SPECS)
        if unknown:
            names = ", ".join(sorted(unknown))
            raise JpegControlValidationError(
                f"unsupported JPEG controls: {names}"
            )
        raw = {
            name: controls.get(name, spec["neutral"])
            for name, spec in JPEG_CONTROL_SPECS.items()
        }
    else:
        raise JpegControlValidationError(
            "JPEG controls must be an object"
        )

    return JpegGlobalControls(
        brightness=_validate_value("brightness", raw["brightness"]),
        contrast=_validate_value("contrast", raw["contrast"]),
        warmth=_validate_value("warmth", raw["warmth"]),
        tint=_validate_value("tint", raw["tint"]),
    )


def jpeg_controls_to_recipe(
    controls: JpegGlobalControls | dict[str, Any],
) -> dict[str, Any]:
    clean = validate_jpeg_controls(controls)

    brightness_gain = 2.0 ** (clean.brightness / 100.0)
    contrast_gain = 1.0 + 0.005 * clean.contrast
    warmth = clean.warmth / 100.0
    tint = clean.tint / 100.0

    channel_gain = np.array(
        [
            1.0 + 0.12 * warmth + 0.06 * tint,
            1.0 - 0.08 * tint,
            1.0 - 0.12 * warmth + 0.06 * tint,
        ],
        dtype=np.float64,
    )
    slopes = brightness_gain * contrast_gain * channel_gain
    bias = np.full(3, 0.5 * (1.0 - contrast_gain), dtype=np.float64)

    coefficients = np.zeros((10, 3), dtype=np.float64)
    coefficients[0, :] = bias
    coefficients[1, 0] = slopes[0]
    coefficients[2, 1] = slopes[1]
    coefficients[3, 2] = slopes[2]

    return build_polynomial_recipe(coefficients)


def jpeg_control_contract() -> dict[str, Any]:
    return {
        "contract_version": JPEG_CONTROL_CONTRACT_VERSION,
        "controls": JPEG_CONTROL_SPECS,
        "raw_equivalence": {
            "temperature_kelvin": False,
            "lightroom_tint": False,
        },
    }
