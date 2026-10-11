"""RAW-CAT-01E.02: conservative syntactic color and opaque-edit inventory.

NOT an Adobe rendering or training-target contract. A present field is not
proof it was applied; a missing field is not equivalent to zero/default.
"""
from __future__ import annotations

import hashlib
import math

_COLORS = ("Red", "Orange", "Yellow", "Green", "Aqua", "Blue", "Purple", "Magenta")

COLOR_FAMILIES: dict[str, frozenset[str]] = {
    "hsl_mixer": frozenset(f"{axis}Adjustment{color}"
        for axis in ("Hue", "Saturation", "Luminance") for color in _COLORS),
    "grayscale_mixer": frozenset(f"GrayMixer{color}" for color in _COLORS),
    "color_grading": frozenset(
        f"ColorGrade{band}{axis}"
        for band in ("Shadow", "Midtone", "Highlight", "Global")
        for axis in ("Hue", "Sat", "Lum")
    ) | frozenset(("ColorGradeBlending", "ColorGradeBalance")),
    "legacy_split_toning": frozenset(
        f"SplitToning{band}{axis}"
        for band in ("Shadow", "Highlight") for axis in ("Hue", "Saturation")
    ) | frozenset(("SplitToningBalance",)),
}

COLOR_FIELDS: frozenset[str] = frozenset().union(*COLOR_FAMILIES.values())

# Blending/Balance can be nonzero in an otherwise ungraded image.
# Keep them in raw numeric coverage, but do not count them as
# nonzero color-adjustment candidates.
GRADING_CONFIGURATION_FIELDS = frozenset(("ColorGradeBlending", "ColorGradeBalance"))

# A fingerprint is deliberately not a parse of profiles, masks or retouch.
OPAQUE_PROFILE_FIELDS = frozenset((
    "Look", "AILook", "CameraProfileDigest", "Preset", "ToggleStyleDigest",
))
OPAQUE_LOCAL_FIELDS = frozenset((
    "MaskGroupBasedCorrections", "RetouchAreas", "RemoveAreas", "RetouchInfo",
    "RedEyeInfo", "FilterList", "PointColors",
))
OPAQUE_FIELDS = OPAQUE_PROFILE_FIELDS | OPAQUE_LOCAL_FIELDS

PROFILE_CONTEXT_FIELDS = frozenset((
    "CameraProfile", "ProcessVersion", "WhiteBalance", "ConvertToGrayscale",
)) | OPAQUE_PROFILE_FIELDS


def parse_color_scalar(name: str, raw: str, *, nested: bool) -> float:
    """Finite numeric extraction only. Preserve absent-vs-explicit-zero upstream."""
    if name not in COLOR_FIELDS:
        raise ValueError("not_a_registered_color_field")
    if nested:
        raise ValueError("nested_color_scalar")
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("invalid_color_scalar") from exc
    if not math.isfinite(value):
        raise ValueError("nonfinite_color_scalar")
    return value


def describe_opaque_field(raw: str, *, nested: bool) -> dict[str, object]:
    """Conservative structural evidence; not an interpretation of active edits.

    No raw metadata, camera look names or mask payloads are copied verbatim.
    """
    trimmed = raw.strip()
    inside = trimmed[1:-1].strip() if nested and trimmed.startswith("{") and trimmed.endswith("}") else trimmed
    nonempty = bool(inside.strip(" \t\r\n,"))
    return {
        "present": True,
        "decoded": False,
        "kind": "opaque_nested_table" if nested else "opaque_scalar",
        "structure_nonempty": nonempty,
        "serialized_length": len(raw),
        "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "lightroom_semantics_validated": False,
    }
