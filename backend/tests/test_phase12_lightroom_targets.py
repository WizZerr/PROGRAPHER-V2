from __future__ import annotations

from pathlib import Path

import pytest

from app.brain_v2.training.lightroom_targets import (
    LightroomTargetExtractionError,
    extract_phase12_target_sample_from_xmp,
)


COMPLETE_XMP = """<?xpacket begin="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description
      xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
      crs:ProcessVersion="11.0"
      crs:WhiteBalance="Custom"
      crs:Temperature="5650"
      crs:Tint="-7"
      crs:Exposure2012="+0.35"
      crs:CameraProfile="Adobe Standard"
      crs:ToneCurveName2012="Medium Contrast"/>
  </rdf:RDF>
</x:xmpmeta>
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "sample.xmp"
    path.write_text(text, encoding="utf-8")
    return path


def test_extracts_complete_phase12_target_sample(tmp_path: Path) -> None:
    result = extract_phase12_target_sample_from_xmp(
        xmp_path=_write(tmp_path, COMPLETE_XMP),
        source_kind="camera_raw",
        preset_identity="none",
    )

    assert result.sample.targets.exposure_stops == pytest.approx(0.35)
    assert result.sample.targets.temperature_k == 5650
    assert result.sample.targets.tint == -7
    assert result.sample.rendering_context.process_version == "11.0"
    assert result.sample.rendering_context.camera_profile == "Adobe Standard"
    assert result.sample.rendering_context.tone_curve == "Medium Contrast"
    assert result.sample.rendering_context.white_balance_mode == "Custom"
    assert result.sample.ready_for_three_target_training is True
    assert result.missing_target_fields == ()


def test_missing_learned_target_stays_missing(tmp_path: Path) -> None:
    xmp = COMPLETE_XMP.replace('      crs:Tint="-7"\n', "")
    result = extract_phase12_target_sample_from_xmp(
        xmp_path=_write(tmp_path, xmp),
        source_kind="camera_raw",
        preset_identity="none",
    )

    assert result.sample.targets.tint is None
    assert result.missing_target_fields == ("tint",)
    assert result.sample.ready_for_three_target_training is False


def test_missing_process_version_is_rejected(tmp_path: Path) -> None:
    xmp = COMPLETE_XMP.replace('      crs:ProcessVersion="11.0"\n', "")
    with pytest.raises(LightroomTargetExtractionError, match="process_version"):
        extract_phase12_target_sample_from_xmp(
            xmp_path=_write(tmp_path, xmp),
            source_kind="camera_raw",
            preset_identity="none",
        )


def test_missing_camera_profile_is_rejected(tmp_path: Path) -> None:
    xmp = COMPLETE_XMP.replace('      crs:CameraProfile="Adobe Standard"\n', "")
    with pytest.raises(LightroomTargetExtractionError, match="camera_profile"):
        extract_phase12_target_sample_from_xmp(
            xmp_path=_write(tmp_path, xmp),
            source_kind="camera_raw",
            preset_identity="none",
        )


def test_tone_curve_can_be_supplied_explicitly(tmp_path: Path) -> None:
    xmp = COMPLETE_XMP.replace(
        '      crs:ToneCurveName2012="Medium Contrast"',
        '',
    )
    result = extract_phase12_target_sample_from_xmp(
        xmp_path=_write(tmp_path, xmp),
        source_kind="camera_raw",
        preset_identity="none",
        tone_curve_identity="known-default",
    )
    assert result.sample.rendering_context.tone_curve == "known-default"


def test_preset_identity_cannot_be_implicit(tmp_path: Path) -> None:
    with pytest.raises(LightroomTargetExtractionError, match="preset_identity"):
        extract_phase12_target_sample_from_xmp(
            xmp_path=_write(tmp_path, COMPLETE_XMP),
            source_kind="camera_raw",
            preset_identity="",
        )


def test_final_temperature_is_not_used_as_as_shot(tmp_path: Path) -> None:
    result = extract_phase12_target_sample_from_xmp(
        xmp_path=_write(tmp_path, COMPLETE_XMP),
        source_kind="camera_raw",
        preset_identity="none",
    )
    ctx = result.sample.rendering_context
    assert ctx.as_shot_temperature_k is None
    assert ctx.as_shot_tint is None
    assert ctx.wb_mapping_reliable is False


def test_known_as_shot_values_can_be_attached_without_guessing(tmp_path: Path) -> None:
    result = extract_phase12_target_sample_from_xmp(
        xmp_path=_write(tmp_path, COMPLETE_XMP),
        source_kind="camera_raw",
        preset_identity="none",
        as_shot_temperature_k=5200,
        as_shot_tint=4,
        wb_mapping_reliable=True,
    )
    ctx = result.sample.rendering_context
    assert ctx.as_shot_temperature_k == 5200
    assert ctx.as_shot_tint == 4
    assert ctx.wb_mapping_reliable is True


def test_malformed_xmp_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(LightroomTargetExtractionError, match="Invalid XMP"):
        extract_phase12_target_sample_from_xmp(
            xmp_path=_write(tmp_path, "<not-closed"),
            source_kind="camera_raw",
            preset_identity="none",
        )
