from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.brain_v2.components import RawInputRecord
from app.brain_v2.contracts import CameraInfo
from app.brain_v2.preprocessing.exiftool_metadata import (
    CameraMetadataResult,
    ExifToolMetadataProvider,
    enrich_raw_input_with_camera_metadata,
)


def _raw(**overrides) -> RawInputRecord:
    payload = {
        "source_fingerprint": "sha256:test",
        "event_id": "event-a",
        "camera": CameraInfo(),
        "captured_at": None,
        "raw_wb": None,
        "exif": {},
        "missing_fields": ("camera_model", "captured_at", "raw_wb"),
        "raw_path": "sample.CR3",
    }
    payload.update(overrides)
    return RawInputRecord(**payload)


def test_exiftool_provider_parses_camera_metadata(tmp_path: Path, monkeypatch) -> None:
    executable = tmp_path / "exiftool.exe"
    executable.write_bytes(b"stub")
    raw_path = tmp_path / "sample.CR3"
    raw_path.write_bytes(b"raw")

    payload = [{
        "Make": "Canon",
        "Model": "Canon EOS R6",
        "LensModel": "RF70-200mm F2.8 L IS USM",
        "DateTimeOriginal": "2021:05:12 12:16:33",
    }]

    def fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )

    monkeypatch.setattr(
        "app.brain_v2.preprocessing.exiftool_metadata.subprocess.run",
        fake_run,
    )

    result = ExifToolMetadataProvider(executable=executable).read(raw_path)

    assert result.state == "available"
    assert result.make == "Canon"
    assert result.model == "Canon EOS R6"
    assert result.lens_model == "RF70-200mm F2.8 L IS USM"
    assert result.captured_at == "2021:05:12 12:16:33"


def test_exiftool_provider_is_explicit_when_executable_missing(tmp_path: Path) -> None:
    raw_path = tmp_path / "sample.CR3"
    raw_path.write_bytes(b"raw")

    result = ExifToolMetadataProvider(
        executable=tmp_path / "missing-exiftool.exe"
    ).read(raw_path)

    assert result.state == "unavailable"
    assert result.reason == "exiftool_executable_not_found"


def test_camera_metadata_enrichment_fills_only_missing_values() -> None:
    raw = _raw()
    metadata = CameraMetadataResult(
        state="available",
        provider_id="test",
        make="Canon",
        model="Canon EOS R6",
        lens_model="RF70-200mm F2.8 L IS USM",
        captured_at="2021:05:12 12:16:33",
    )

    enriched = enrich_raw_input_with_camera_metadata(raw, metadata)

    assert enriched.camera.make == "Canon"
    assert enriched.camera.model == "Canon EOS R6"
    assert enriched.captured_at == "2021:05:12 12:16:33"
    assert enriched.exif["lens_model"] == "RF70-200mm F2.8 L IS USM"
    assert "camera_model" not in enriched.missing_fields
    assert "captured_at" not in enriched.missing_fields
    assert "raw_wb" in enriched.missing_fields


def test_camera_metadata_enrichment_does_not_override_known_source_values() -> None:
    raw = _raw(
        camera=CameraInfo(make="Existing Make", model="Existing Model"),
        captured_at="existing-time",
        exif={"lens_model": "Existing Lens"},
        missing_fields=("raw_wb",),
    )
    metadata = CameraMetadataResult(
        state="available",
        provider_id="test",
        make="Canon",
        model="Canon EOS R6",
        lens_model="RF70-200mm F2.8 L IS USM",
        captured_at="2021:05:12 12:16:33",
    )

    enriched = enrich_raw_input_with_camera_metadata(raw, metadata)

    assert enriched.camera.make == "Existing Make"
    assert enriched.camera.model == "Existing Model"
    assert enriched.captured_at == "existing-time"
    assert enriched.exif["lens_model"] == "Existing Lens"
