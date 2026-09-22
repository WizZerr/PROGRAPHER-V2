from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import xml.etree.ElementTree as ET

from app.brain_v2.models.edit_targets import (
    LightroomEditTargets,
    LightroomRenderingContext,
    Phase12TargetSample,
)

CRS_NS = "http://ns.adobe.com/camera-raw-settings/1.0/"
CRS = f"{{{CRS_NS}}}"


@dataclass(frozen=True)
class LightroomTargetExtraction:
    sample: Phase12TargetSample
    source_xmp: str
    extracted_fields: tuple[str, ...]
    missing_target_fields: tuple[str, ...]


class LightroomTargetExtractionError(ValueError):
    pass


def _all_crs_values(root: ET.Element) -> dict[str, str]:
    values: dict[str, str] = {}
    for element in root.iter():
        for key, value in element.attrib.items():
            if key.startswith(CRS):
                values[key[len(CRS):]] = value.strip()
        if element.tag.startswith(CRS) and element.text:
            values[element.tag[len(CRS):]] = element.text.strip()
    return values


def _parse_float(value: str | None, field: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise LightroomTargetExtractionError(
            f"Invalid Lightroom {field} value: {value!r}"
        ) from exc


def _parse_int(value: str | None, field: str) -> int | None:
    parsed = _parse_float(value, field)
    if parsed is None:
        return None
    rounded = round(parsed)
    if abs(parsed - rounded) > 1e-9:
        raise LightroomTargetExtractionError(
            f"Lightroom {field} must be integral, got {value!r}"
        )
    return int(rounded)


def extract_phase12_target_sample_from_xmp(
    *,
    xmp_path: str | Path,
    source_kind: Literal["camera_raw", "dng_raw"],
    preset_identity: str,
    tone_curve_identity: str | None = None,
    as_shot_temperature_k: int | None = None,
    as_shot_tint: int | None = None,
    wb_mapping_reliable: bool = False,
) -> LightroomTargetExtraction:
    path = Path(xmp_path).resolve()
    if not path.is_file():
        raise LightroomTargetExtractionError(f"XMP file not found: {path}")

    if not preset_identity or not preset_identity.strip():
        raise LightroomTargetExtractionError(
            "preset_identity must be explicit; use 'none' only when that is known"
        )

    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise LightroomTargetExtractionError(
            f"Invalid XMP/XML file: {path}: {exc}"
        ) from exc

    crs = _all_crs_values(root)

    exposure_raw = crs.get("Exposure2012")
    if exposure_raw is None:
        exposure_raw = crs.get("Exposure")

    temperature_raw = crs.get("Temperature")
    tint_raw = crs.get("Tint")

    process_version = (crs.get("ProcessVersion") or "").strip()
    camera_profile = (crs.get("CameraProfile") or "").strip()

    xmp_tone_curve = (
        (crs.get("ToneCurveName2012") or "").strip()
        or (crs.get("ToneCurveName") or "").strip()
    )
    tone_curve = (tone_curve_identity or "").strip() or xmp_tone_curve

    missing_context: list[str] = []
    if not process_version:
        missing_context.append("process_version")
    if not camera_profile:
        missing_context.append("camera_profile")
    if not tone_curve:
        missing_context.append("tone_curve")

    if missing_context:
        raise LightroomTargetExtractionError(
            "Missing required Lightroom rendering context: "
            + ", ".join(missing_context)
        )

    targets = LightroomEditTargets(
        exposure_stops=_parse_float(exposure_raw, "Exposure"),
        temperature_k=_parse_int(temperature_raw, "Temperature"),
        tint=_parse_int(tint_raw, "Tint"),
    )

    rendering_context = LightroomRenderingContext(
        source_kind=source_kind,
        process_version=process_version,
        camera_profile=camera_profile,
        tone_curve=tone_curve,
        preset_identity=preset_identity.strip(),
        white_balance_mode=(crs.get("WhiteBalance") or None),
        as_shot_temperature_k=as_shot_temperature_k,
        as_shot_tint=as_shot_tint,
        wb_mapping_reliable=wb_mapping_reliable,
    )

    extracted_fields = tuple(
        sorted(
            name
            for name, raw_value in (
                ("exposure_stops", exposure_raw),
                ("temperature_k", temperature_raw),
                ("tint", tint_raw),
                ("process_version", process_version),
                ("camera_profile", camera_profile),
                ("tone_curve", tone_curve),
                ("white_balance_mode", crs.get("WhiteBalance")),
            )
            if raw_value not in (None, "")
        )
    )

    sample = Phase12TargetSample(
        targets=targets,
        rendering_context=rendering_context,
    )

    return LightroomTargetExtraction(
        sample=sample,
        source_xmp=str(path),
        extracted_fields=extracted_fields,
        missing_target_fields=targets.missing_fields,
    )
