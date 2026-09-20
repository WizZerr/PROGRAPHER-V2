from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

import exifread

from app.datasets.contracts import SourceMetadata


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def _ratio_to_float(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, Fraction):
        return float(value)

    numerator = getattr(value, "num", None)
    denominator = getattr(value, "den", None)

    if numerator is not None and denominator not in (None, 0):
        return float(numerator) / float(denominator)

    text = _clean_text(value)
    if not text:
        return None

    try:
        if "/" in text:
            left, right = text.split("/", 1)
            return float(left) / float(right)
        return float(text)
    except (ValueError, ZeroDivisionError):
        return None


def _first_value(tag: Any) -> Any:
    values = getattr(tag, "values", None)

    if isinstance(values, list) and values:
        return values[0]

    return tag


def _int_tag(tags: dict[str, Any], *names: str) -> int | None:
    for name in names:
        tag = tags.get(name)
        if tag is None:
            continue

        value = _ratio_to_float(_first_value(tag))
        if value is not None:
            return int(round(value))

    return None


def _float_tag(tags: dict[str, Any], *names: str) -> float | None:
    for name in names:
        tag = tags.get(name)
        if tag is None:
            continue

        value = _ratio_to_float(_first_value(tag))
        if value is not None:
            return value

    return None


def _text_tag(tags: dict[str, Any], *names: str) -> str | None:
    for name in names:
        tag = tags.get(name)
        if tag is None:
            continue

        value = _clean_text(tag)
        if value:
            return value

    return None


def _wb_values(tags: dict[str, Any]) -> tuple[tuple[float, ...], str] | None:
    # RAW WB metadata is vendor-specific. We record it only when a tag is
    # actually present; absence remains None and is never converted to zero.
    candidates = (
        "MakerNote WB RGGB Levels",
        "MakerNote WB RB Levels",
        "MakerNote White Balance",
        "Image AsShotNeutral",
    )

    for name in candidates:
        tag = tags.get(name)
        if tag is None:
            continue

        raw_values = getattr(tag, "values", None)
        if not isinstance(raw_values, list):
            raw_values = [raw_values if raw_values is not None else tag]

        parsed: list[float] = []
        for item in raw_values:
            value = _ratio_to_float(item)
            if value is not None:
                parsed.append(value)

        if parsed:
            return tuple(parsed), name

    return None


def extract_source_metadata(path: str | Path) -> SourceMetadata:
    source = Path(path)

    try:
        with source.open("rb") as handle:
            tags = exifread.process_file(
                handle,
                details=False,
                strict=False,
            )
    except (OSError, ValueError, TypeError):
        return SourceMetadata()

    wb = _wb_values(tags)

    shutter = _float_tag(
        tags,
        "EXIF ExposureTime",
        "Image ExposureTime",
    )

    aperture = _float_tag(
        tags,
        "EXIF FNumber",
        "Image FNumber",
    )

    focal = _float_tag(
        tags,
        "EXIF FocalLength",
        "Image FocalLength",
    )

    return SourceMetadata(
        camera_make=_text_tag(
            tags,
            "Image Make",
            "EXIF Make",
        ),
        camera_model=_text_tag(
            tags,
            "Image Model",
            "EXIF Model",
        ),
        captured_at=_text_tag(
            tags,
            "EXIF DateTimeOriginal",
            "EXIF DateTimeDigitized",
            "Image DateTime",
        ),
        iso=_int_tag(
            tags,
            "EXIF ISOSpeedRatings",
            "EXIF PhotographicSensitivity",
        ),
        shutter_seconds=shutter,
        aperture=aperture,
        focal_length_mm=focal,
        raw_wb=wb[0] if wb else None,
        raw_wb_source=wb[1] if wb else None,
    )
